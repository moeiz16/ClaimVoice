"""§1.7 claims: the ledger, the claim file, corrections, assignment, recording, photos, "Where it goes" (accept or
change the route with a reason), closer-look referrals; and the public photo-link upload (`/p/{token}`).

Nobody can approve or deny a claim here: routing only decides who looks first."""

from __future__ import annotations

import asyncio
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

from litestar import Response, Router, get, patch, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.params import Body, Parameter
from sqlalchemy import Select, String, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from claimvoice import clock
from claimvoice.api import labels
from claimvoice.api.context import Ctx, not_found, paged
from claimvoice.api.routes.calls import audio_for, recording_for
from claimvoice.calls import views as call_views
from claimvoice.calls.models import Call, CallSlot, PhotoLink
from claimvoice.claims import views
from claimvoice.claims.models import Claim, ClaimPhoto, RoutingDecisionRow, SiuReferral
from claimvoice.config import get_settings
from claimvoice.dialogue.slots import SLOT_CATALOG, display
from claimvoice.platform.db import new_id
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.events import bus, org_key
from claimvoice.platform.models import Membership, Organization, User
from claimvoice.platform.security import token_digest
from claimvoice.policies.models import Policy, Policyholder
from claimvoice.schemas import claims as w
from claimvoice.schemas.base import Page
from claimvoice.schemas.calls import ClaimFile, Transcript

PHOTO_MAX_BYTES = 10 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/heic": ".heic", "image/webp": ".webp"}


def _invalid(field: str, message: str) -> ProblemError:
    return ProblemError(
        422,
        "validation_error",
        "Validation failed",
        "One or more fields are invalid.",
        errors=[{"field": field, "message": message}],
    )


async def _claim(ctx: Ctx, claim_id: str) -> Claim:
    return await ctx.get(Claim, claim_id)


async def _publish(ctx: Ctx, claim: Claim, type_: str = "claim.updated") -> None:
    summary = (await views.summaries(ctx.db, [claim], "en", siu=True))[0]
    bus.publish(org_key(ctx.org_id), type_, summary, org_id=ctx.org_id, call_id=claim.call_id)


# ---------------------------------------------------------------- ledger and detail


@get("/claims")
async def list_claims(
    ctx: Ctx,
    page: int = 1,
    page_size: int | None = Parameter(query="pageSize", default=None),
    status: str | None = None,
    route: str | None = None,
    loss_type: str | None = Parameter(query="lossType", default=None),
    line: str | None = None,
    region: str | None = None,
    assigned: str | None = None,
    flag: str | None = None,
    surge: str | None = None,
    from_: str | None = Parameter(query="from", default=None),
    to: str | None = None,
    q: str | None = None,
) -> Page[w.ClaimSummary]:
    ctx.require("claims:read")
    stmt: Select[Any] = select(Claim).where(Claim.org_id == ctx.org_id)
    if status and status != "all":
        stmt = stmt.where(Claim.status == status)
    if route:
        stmt = stmt.where(Claim.id.in_(select(RoutingDecisionRow.claim_id).where(RoutingDecisionRow.route == route)))
    if loss_type:
        stmt = stmt.where(Claim.loss_type == loss_type)
    if line:
        stmt = stmt.where(Claim.line == line)
    if region:
        stmt = stmt.where(Claim.policy_id.in_(select(Policy.id).where(Policy.region == region)))
    if assigned == "me":
        stmt = stmt.where(Claim.assigned_to == ctx.user.id)
    elif assigned == "none":
        stmt = stmt.where(Claim.assigned_to.is_(None))
    elif assigned:
        stmt = stmt.where(Claim.assigned_to == assigned)
    if flag == "urgent_safety":
        stmt = stmt.where(Claim.urgent_safety.is_(True))
    elif flag == "siu" and ctx.siu:
        open_ids = select(SiuReferral.claim_id).where(SiuReferral.status.in_(("open", "investigating")))
        stmt = stmt.where(Claim.id.in_(open_ids))
    if surge:
        stmt = stmt.where(Claim.surge_id == surge)
    for value, op in ((from_, ">="), (to, "<=")):
        if value:
            try:
                dt = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ProblemError(400, "bad_request", "Bad request", "Dates must be ISO dates or times.") from exc
            dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            stmt = stmt.where(Claim.reported_at >= dt if op == ">=" else Claim.reported_at <= dt)
    if q:
        like = f"%{q.strip()}%"
        holders = select(Policyholder.id).where(Policyholder.org_id == ctx.org_id, Policyholder.full_name.ilike(like))
        policies = select(Policy.id).where(Policy.org_id == ctx.org_id, Policy.policy_number.ilike(like))
        stmt = stmt.where(
            or_(Claim.claim_number.ilike(like), Claim.holder_id.in_(holders), Claim.policy_id.in_(policies))
        )
    stmt = stmt.order_by(Claim.reported_at.desc())

    async def mapper(rows: Sequence[Claim]) -> list[w.ClaimSummary]:
        return await views.summaries(ctx.db, rows, ctx.lang, siu=ctx.siu)

    return await paged(ctx.db, stmt, page, page_size, mapper)


@get("/claims/{claim_id:str}")
async def get_claim(ctx: Ctx, claim_id: str) -> w.Claim:
    ctx.require("claims:read")
    return await views.detail(ctx.db, await _claim(ctx, claim_id), ctx.lang, siu=ctx.siu)


@patch("/claims/{claim_id:str}")
async def update_claim(ctx: Ctx, claim_id: str, data: w.ClaimUpdateIn) -> w.Claim:
    ctx.require("claims:edit")
    claim = await _claim(ctx, claim_id)
    if data.status is not None and data.status != claim.status:
        before = claim.status
        claim.status = data.status
        await ctx.db.commit()
        await ctx.audit(
            "claim.status_changed",
            f"{ctx.user.full_name} moved {claim.claim_number} from "
            f"{labels.pick(labels.CLAIM_STATUSES[before], 'en').lower()} to "
            f"{labels.pick(labels.CLAIM_STATUSES[claim.status], 'en').lower()}.",
            target_type="claim",
            target_id=claim.id,
            target_label=claim.claim_number,
            details={"from": before, "to": claim.status},
        )
        await _publish(ctx, claim)
    return await views.detail(ctx.db, claim, ctx.lang, siu=ctx.siu)


@post("/claims/{claim_id:str}/assign", status_code=200)
async def assign(ctx: Ctx, claim_id: str, data: w.AssignIn) -> w.Claim:
    ctx.require("claims:assign")
    claim = await _claim(ctx, claim_id)
    who = None
    if data.user_id is not None:
        member = (
            await ctx.db.execute(
                select(Membership).where(Membership.org_id == ctx.org_id, Membership.user_id == data.user_id)
            )
        ).scalar_one_or_none()
        if member is None:
            raise _invalid("userId", "Choose someone in your organisation.")
        who = await ctx.db.get(User, data.user_id)
    claim.assigned_to = data.user_id
    if data.user_id and claim.status == "new":
        claim.status = "assigned"
    await ctx.db.commit()
    text = f"assigned {claim.claim_number} to {who.full_name}" if who else f"unassigned {claim.claim_number}"
    await ctx.audit(
        "claim.assigned",
        f"{ctx.user.full_name} {text}.",
        target_type="claim",
        target_id=claim.id,
        target_label=claim.claim_number,
        details={"userId": data.user_id},
    )
    await _publish(ctx, claim)
    return await views.detail(ctx.db, claim, ctx.lang, siu=ctx.siu)


async def _claim_call(ctx: Ctx, claim: Claim) -> Call:
    call = await ctx.db.get(Call, claim.call_id) if claim.call_id else None
    if call is None:
        raise not_found()
    return call


@get("/claims/{claim_id:str}/transcript")
async def claim_transcript(ctx: Ctx, claim_id: str) -> Transcript:
    ctx.require("claims:read")
    return await call_views.transcript(ctx.db, await _claim_call(ctx, await _claim(ctx, claim_id)), ctx.lang)


@patch("/claims/{claim_id:str}/file")
async def edit_file(ctx: Ctx, claim_id: str, data: w.FileEditIn) -> ClaimFile:
    ctx.require("claims:edit")
    claim = await _claim(ctx, claim_id)
    call = await _claim_call(ctx, claim)
    if not data.slots:
        raise _invalid("slots", "Change at least one value.")
    now = clock.now()
    changed = []
    for i, edit in enumerate(data.slots):
        if edit.key not in SLOT_CATALOG:
            raise _invalid(f"slots[{i}].key", "That isn't a claim-file field.")
        if not edit.note or not edit.note.strip():
            raise _invalid(f"slots[{i}].note", "Say why it changed.")
        value: Any = edit.value
        if isinstance(value, str):
            value = value.strip()[:500]
        spec = SLOT_CATALOG[edit.key]
        if spec.kind == "yes_no" and not isinstance(value, bool | None):
            raise _invalid(f"slots[{i}].value", "Choose yes or no.")
        if spec.kind == "date" and isinstance(value, str):
            try:
                datetime.fromisoformat(value)
            except ValueError as exc:
                raise _invalid(f"slots[{i}].value", "Use a date like 2026-01-08.") from exc
        await ctx.db.execute(
            update(CallSlot)
            .where(CallSlot.call_id == call.id, CallSlot.key == edit.key, CallSlot.superseded_at.is_(None))
            .values(superseded_at=now)
        )
        ctx.db.add(
            CallSlot(
                org_id=ctx.org_id,
                call_id=call.id,
                key=edit.key,
                value=value,
                display=display(edit.key, value, claim.language),
                confidence=None,
                source="person",
                changed_by=ctx.user.full_name,
                note=edit.note.strip()[:500],
                created_at=now,
                confirmed=True,
            )
        )
        changed.append(spec.en)
    await ctx.db.commit()
    await ctx.audit(
        "claim.file_edited",
        f"{ctx.user.full_name} corrected {', '.join(changed)} on {claim.claim_number}; the heard values "
        "are kept in the history.",
        target_type="claim",
        target_id=claim.id,
        target_label=claim.claim_number,
        details={"keys": [s.key for s in data.slots]},
    )
    await _publish(ctx, claim)
    return await call_views.claim_file(ctx.db, call, ctx.lang, claim_id=claim.id)


@get("/claims/{claim_id:str}/recording")
async def claim_recording(ctx: Ctx, claim_id: str) -> w.Recording:
    ctx.require("recordings:read")
    claim = await _claim(ctx, claim_id)
    call = await _claim_call(ctx, claim)
    rec = await recording_for(ctx, call)
    if rec.audio_url:
        rec.audio_url = f"/api/v1/claims/{claim.id}/recording/audio"
    return rec


@get("/claims/{claim_id:str}/recording/audio")
async def claim_audio(ctx: Ctx, claim_id: str) -> Response[bytes]:
    ctx.require("recordings:read")
    claim = await _claim(ctx, claim_id)
    call = await _claim_call(ctx, claim)
    return await audio_for(ctx, call, ("claim", claim.id, claim.claim_number))


# ---------------------------------------------------------------- photos


@get("/claims/{claim_id:str}/photos")
async def list_photos(ctx: Ctx, claim_id: str) -> list[w.Photo]:
    ctx.require("claims:read")
    claim = await _claim(ctx, claim_id)
    rows = (
        (
            await ctx.db.execute(
                select(ClaimPhoto).where(ClaimPhoto.claim_id == claim.id).order_by(ClaimPhoto.received_at)
            )
        )
        .scalars()
        .all()
    )
    return [views.photo_out(p) for p in rows]


def _photo_file(rel: str) -> Any:
    base = get_settings().uploads_dir.resolve()
    path = (base / rel).resolve()
    if base not in path.parents or not path.is_file():
        raise not_found()
    return path


@get("/photos/{photo_id:str}")
async def photo(ctx: Ctx, photo_id: str) -> Response[bytes]:
    ctx.require("claims:read")
    p = await ctx.get(ClaimPhoto, photo_id)
    path = _photo_file(p.path)
    return Response(path.read_bytes(), media_type=p.content_type, headers={"Cache-Control": "private, max-age=300"})


@get("/photos/{photo_id:str}/thumbnail")
async def photo_thumbnail(ctx: Ctx, photo_id: str) -> Response[bytes]:
    ctx.require("claims:read")
    p = await ctx.get(ClaimPhoto, photo_id)
    path = _photo_file(p.thumbnail_path)
    media = "image/jpeg" if path.suffix == ".jpg" else p.content_type
    return Response(path.read_bytes(), media_type=media, headers={"Cache-Control": "private, max-age=300"})


async def _open_link(db: AsyncSession, token: str) -> PhotoLink:
    link = (await db.execute(select(PhotoLink).where(PhotoLink.token_hash == token_digest(token)))).scalar_one_or_none()
    if link is None:
        raise not_found()
    if clock.real_now() >= link.expires_at:
        raise ProblemError(410, "expired", "This photo link has expired", "Call us and we'll text a new one.")
    return link


async def _uploaded(db: AsyncSession, link: PhotoLink) -> int:
    return int(
        (
            await db.execute(select(func.count()).select_from(ClaimPhoto).where(ClaimPhoto.call_id == link.call_id))
        ).scalar_one()
    )


@get("/photo-links/{token:str}")
async def photo_link(db_session: AsyncSession, token: str) -> dict[str, Any]:
    link = await _open_link(db_session, token)
    call = await db_session.get(Call, link.call_id)
    org = await db_session.get(Organization, link.org_id)
    assert call is not None
    assert org is not None
    claim = await db_session.get(Claim, link.claim_id) if link.claim_id else None
    return {
        "orgName": org.name,
        "claimReference": claim.claim_number if claim else (call.claim_number or call.reference),
        "language": "fr" if call.language == "fr" else "en",
        "expiresAt": link.expires_at.isoformat(),
        "maxPhotos": link.max_photos,
        "uploaded": await _uploaded(db_session, link),
    }


@dataclass
class PhotoForm:
    file: UploadFile
    caption: str | None = None


def _process_image(raw: bytes, content_type: str) -> tuple[bytes, bytes, int, int]:
    """Re-encode without metadata (removes EXIF location) and make a 480 px thumbnail."""
    from PIL import Image, UnidentifiedImageError

    try:
        img: Image.Image = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ProblemError(
            415, "unsupported_media_type", "Unsupported file type", "Send a JPEG, PNG, HEIC or WebP photo."
        ) from exc
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img) or img
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")
    clean = Image.frombytes(img.mode, img.size, img.tobytes())  # pixels only: no EXIF, GPS or other metadata
    out = io.BytesIO()
    fmt = {"image/png": "PNG", "image/webp": "WEBP"}.get(content_type, "JPEG")
    (clean.convert("RGB") if fmt == "JPEG" else clean).save(out, format=fmt, quality=88)
    thumb = clean.convert("RGB")
    thumb.thumbnail((480, 480))
    tout = io.BytesIO()
    thumb.save(tout, format="JPEG", quality=80)
    return out.getvalue(), tout.getvalue(), img.size[0], img.size[1]


@post("/photo-links/{token:str}/photos", status_code=201, request_max_body_size=PHOTO_MAX_BYTES + 512 * 1024)
async def upload_photo(
    db_session: AsyncSession,
    token: str,
    data: Annotated[PhotoForm, Body(media_type=RequestEncodingType.MULTI_PART)],
) -> w.Photo:
    link = await _open_link(db_session, token)
    if await _uploaded(db_session, link) >= link.max_photos:
        raise ProblemError(
            409,
            "already_decided",
            "That's the most photos for this link",
            f"Up to {link.max_photos} photos can be sent with one link.",
        )
    content_type = (data.file.content_type or "").lower()
    if content_type not in PHOTO_TYPES:
        raise ProblemError(
            415, "unsupported_media_type", "Unsupported file type", "Send a JPEG, PNG, HEIC or WebP photo."
        )
    raw = await data.file.read()
    if len(raw) > PHOTO_MAX_BYTES:
        raise ProblemError(413, "payload_too_large", "That photo is too large", "Send photos up to 10 MB.")
    if content_type == "image/heic":
        # There is no offline HEIC decoder, so its location data could not be removed: ask for a JPEG instead.
        raise ProblemError(
            415,
            "unsupported_media_type",
            "Unsupported file type",
            "This phone sent a HEIC photo. Choose 'Most compatible' or send a JPEG.",
        )
    body, thumb, width, height = await asyncio.to_thread(_process_image, raw, content_type)
    photo_id = new_id()
    folder = get_settings().uploads_dir / link.org_id
    folder.mkdir(parents=True, exist_ok=True)
    ext = PHOTO_TYPES[content_type]
    (folder / f"{photo_id}{ext}").write_bytes(body)
    (folder / f"{photo_id}-thumb.jpg").write_bytes(thumb)
    caption = " ".join((data.caption or "").split())[:280] or None
    row = ClaimPhoto(
        id=photo_id,
        org_id=link.org_id,
        claim_id=link.claim_id,
        call_id=link.call_id,
        path=f"{link.org_id}/{photo_id}{ext}",
        thumbnail_path=f"{link.org_id}/{photo_id}-thumb.jpg",
        content_type=content_type,
        caption=caption,
        width=width,
        height=height,
        source="text_link",
        received_at=clock.now(),
    )
    db_session.add(row)
    await db_session.commit()
    if link.claim_id:
        claim = await db_session.get(Claim, link.claim_id)
        if claim is not None:
            summary = (await views.summaries(db_session, [claim], "en", siu=True))[0]
            bus.publish(org_key(link.org_id), "claim.updated", summary, org_id=link.org_id, call_id=link.call_id)
    return views.photo_out(row)


# ---------------------------------------------------------------- where it goes


async def _routing(ctx: Ctx, claim: Claim) -> RoutingDecisionRow:
    row = (
        await ctx.db.execute(select(RoutingDecisionRow).where(RoutingDecisionRow.claim_id == claim.id))
    ).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row


async def _routing_out(ctx: Ctx, row: RoutingDecisionRow, claim: Claim) -> w.RoutingDecision:
    people = await call_views.users_by_id(ctx.db, [row.accepted_by, row.override_by])
    return views.routing_out(row, claim, ctx.lang, siu=ctx.siu, people=people)


@get("/claims/{claim_id:str}/routing")
async def get_routing(ctx: Ctx, claim_id: str) -> w.RoutingDecision:
    ctx.require("claims:read")
    claim = await _claim(ctx, claim_id)
    return await _routing_out(ctx, await _routing(ctx, claim), claim)


@post("/claims/{claim_id:str}/routing/accept", status_code=200)
async def accept_route(ctx: Ctx, claim_id: str) -> w.RoutingDecision:
    ctx.require("claims:route")
    claim = await _claim(ctx, claim_id)
    row = await _routing(ctx, claim)
    if row.accepted_at is not None or row.override_at is not None:
        raise ProblemError(
            409, "already_decided", "Already decided", "Someone has already accepted or changed this route."
        )
    row.accepted_by, row.accepted_at = ctx.user.id, clock.now()
    await ctx.db.commit()
    await ctx.audit(
        "claim.route_accepted",
        f"{ctx.user.full_name} accepted the {labels.route(row.route, 'en')} route for {claim.claim_number}.",
        target_type="claim",
        target_id=claim.id,
        target_label=claim.claim_number,
        details={"route": row.route},
    )
    await _publish(ctx, claim, "claim.routed")
    return await _routing_out(ctx, row, claim)


@post("/claims/{claim_id:str}/routing/override", status_code=200)
async def override_route(ctx: Ctx, claim_id: str, data: w.RouteOverrideIn) -> w.RoutingDecision:
    ctx.require("claims:route")
    claim = await _claim(ctx, claim_id)
    row = await _routing(ctx, claim)
    reason = " ".join(data.reason.split())
    if not reason:
        raise _invalid("reason", "Give a reason for the change.")
    if data.route == row.route:
        raise _invalid("route", "Choose a different route.")
    before = row.route
    row.override_route, row.override_reason = data.route, reason[:500]
    row.override_by, row.override_at = ctx.user.id, clock.now()
    row.route = data.route
    if data.route == "special_investigation":
        referral = (
            await ctx.db.execute(select(SiuReferral).where(SiuReferral.claim_id == claim.id))
        ).scalar_one_or_none()
        if referral is None:
            ctx.db.add(
                SiuReferral(
                    org_id=ctx.org_id,
                    claim_id=claim.id,
                    status="open",
                    score=row.fraud_score,
                    indicators=row.fraud_indicators,
                    opened_at=clock.now(),
                    note=reason[:500],
                )
            )
    await ctx.db.commit()
    await ctx.audit(
        "claim.route_override",
        f"{ctx.user.full_name} changed {claim.claim_number} from {labels.route(before, 'en')} to "
        f"{labels.route(data.route, 'en')}: “{reason}”",
        target_type="claim",
        target_id=claim.id,
        target_label=claim.claim_number,
        details={"from": before, "to": data.route, "reason": reason},
    )
    await _publish(ctx, claim, "claim.routed")
    return await _routing_out(ctx, row, claim)


# ---------------------------------------------------------------- closer-look referrals


@get("/claims/{claim_id:str}/siu")
async def get_siu(ctx: Ctx, claim_id: str) -> w.SiuReferral:
    ctx.require("siu:read")
    claim = await _claim(ctx, claim_id)
    s = (await ctx.db.execute(select(SiuReferral).where(SiuReferral.claim_id == claim.id))).scalar_one_or_none()
    if s is None:
        raise not_found()
    people = await call_views.users_by_id(ctx.db, [s.decided_by])
    return views.siu_out(s, claim, ctx.lang, people)


DECISIONS = {
    "investigate": "investigating",
    "close_no_concern": "closed_no_concern",
    "return_to_adjuster": "returned_to_adjuster",
}


@post("/claims/{claim_id:str}/siu/decision", status_code=200)
async def siu_decision(ctx: Ctx, claim_id: str, data: w.SiuDecisionIn) -> w.SiuReferral:
    ctx.require("siu:decide")
    claim = await _claim(ctx, claim_id)
    s = (await ctx.db.execute(select(SiuReferral).where(SiuReferral.claim_id == claim.id))).scalar_one_or_none()
    if s is None:
        raise not_found()
    if s.status in ("closed_no_concern", "returned_to_adjuster"):
        raise ProblemError(409, "already_decided", "Already decided", "This referral has already been closed.")
    note = " ".join(data.note.split())
    if not note:
        raise _invalid("note", "Add a short note for the file.")
    s.status, s.decided_by, s.decided_at, s.note = DECISIONS[data.decision], ctx.user.id, clock.now(), note[:1000]
    await ctx.db.commit()
    await ctx.audit(
        "siu.decision",
        f"{ctx.user.full_name} marked the closer-look referral on {claim.claim_number} "
        f"“{labels.pick(labels.SIU_STATUSES[s.status], 'en').lower()}”.",
        target_type="claim",
        target_id=claim.id,
        target_label=claim.claim_number,
        details={"decision": data.decision},
    )
    await _publish(ctx, claim)
    people = await call_views.users_by_id(ctx.db, [s.decided_by])
    return views.siu_out(s, claim, ctx.lang, people)


@get("/siu/referrals")
async def list_referrals(
    ctx: Ctx,
    page: int = 1,
    page_size: int | None = Parameter(query="pageSize", default=None),
    status: str | None = None,
) -> Page[w.SiuReferral]:
    ctx.require("siu:read")
    stmt: Select[Any] = select(SiuReferral).where(SiuReferral.org_id == ctx.org_id)
    if status and status != "all":
        stmt = stmt.where(SiuReferral.status == status)
    open_first = cast(SiuReferral.status.in_(("open", "investigating")), String)
    stmt = stmt.order_by(open_first.desc(), SiuReferral.opened_at.desc())

    async def mapper(rows: Sequence[SiuReferral]) -> list[w.SiuReferral]:
        claims = {
            c.id: c
            for c in (await ctx.db.execute(select(Claim).where(Claim.id.in_([r.claim_id for r in rows])))).scalars()
        }
        people = await call_views.users_by_id(ctx.db, [r.decided_by for r in rows])
        return [views.siu_out(r, claims[r.claim_id], ctx.lang, people) for r in rows if r.claim_id in claims]

    return await paged(ctx.db, stmt, page, page_size, mapper)


ROUTER = Router(
    path="/api/v1",
    route_handlers=[
        list_claims,
        get_claim,
        update_claim,
        assign,
        claim_transcript,
        edit_file,
        claim_recording,
        claim_audio,
        list_photos,
        photo,
        photo_thumbnail,
        photo_link,
        upload_photo,
        get_routing,
        accept_route,
        override_route,
        get_siu,
        siu_decision,
        list_referrals,
    ],
)
