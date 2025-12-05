"""§1.10 routing checks: the page, fact sheets, fairness, two-person sign-off and the pack for the regulator."""

from __future__ import annotations

from litestar import Response, Router, get, post

from claimvoice.api.context import Ctx, not_found
from claimvoice.claims import checks
from claimvoice.platform.errors import ProblemError
from claimvoice.platform.permissions import SIGNOFF_SIDE, Role
from claimvoice.schemas import ml as w


def _key(check: str) -> str:
    if check not in checks.CHECK_ORDER:
        raise not_found()
    return check


@get("/routing-checks")
async def routing_checks(ctx: Ctx) -> w.RoutingChecks:
    ctx.require("models:read")
    return await checks.page(ctx.db, ctx.org_id)


@get("/routing-checks/regulator-pack")
async def regulator_pack(ctx: Ctx) -> Response[bytes]:
    ctx.require("models:read")
    body = await checks.regulator_pack(ctx.db, ctx.org_id, ctx.org.name)
    await ctx.audit(
        "check.regulator_pack",
        f"{ctx.user.full_name} downloaded the pack for the regulator.",
        target_type="routing_checks",
        target_id="pack",
        target_label="Pack for the regulator",
    )
    return Response(
        body,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="claimvoice-routing-checks-pack.zip"'},
    )


@get("/routing-checks/{check:str}")
async def fact_sheet(ctx: Ctx, check: str) -> w.FactSheet:
    ctx.require("models:read")
    sheet = await checks.fact_sheet(ctx.db, ctx.org_id, _key(check))
    if sheet is None:
        raise not_found()
    return sheet


@get("/routing-checks/{check:str}/fairness")
async def fairness(ctx: Ctx, check: str, version: int | None = None) -> w.Fairness:
    ctx.require("models:read")
    out = await checks.fairness(ctx.db, ctx.org_id, _key(check), version)
    if out is None:
        raise not_found()
    return out


@post("/routing-checks/{check:str}/versions/{version:int}/sign-off", status_code=200)
async def sign_off(ctx: Ctx, check: str, version: int, data: w.SignOffIn) -> w.Check:
    ctx.require("models:signoff")
    key = _key(check)
    if data.version != version:
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "version", "message": "The version doesn't match the page."}],
        )
    note = " ".join(data.note.split())
    if not note:
        raise ProblemError(
            422,
            "validation_error",
            "Validation failed",
            errors=[{"field": "note", "message": "Write the sign-off statement."}],
        )
    side = SIGNOFF_SIDE.get(Role(ctx.membership.role))
    if side is None:
        raise ProblemError(403, "forbidden", "Not allowed", "Your role doesn't sign routing checks.")
    try:
        promoted = await checks.sign(ctx.db, ctx.org_id, key, version, side=side, user_id=ctx.user.id, note=note[:1000])
    except LookupError as exc:
        raise not_found() from exc
    except checks.SignOffError as exc:
        raise ProblemError(409, exc.code, "Can't sign this version", str(exc)) from exc
    await ctx.db.commit()
    name = "size check" if key == "size" else "closer-look check"
    await ctx.audit(
        "check.signed_off",
        f"{ctx.user.full_name} signed off version {version} of the {name} for "
        f"{checks.SIDE_LABELS[side].lower()}: “{note}”",
        target_type="routing_check",
        target_id=key,
        target_label=f"{name.capitalize()} v{version}",
        details={"side": side, "version": version},
    )
    if promoted:
        await ctx.audit(
            "check.version_in_use",
            f"Version {version} of the {name} went into use after two sign-offs; the previous version was retired.",
            target_type="routing_check",
            target_id=key,
            target_label=f"{name.capitalize()} v{version}",
            details={"version": version},
        )
    out = await checks.check_out(ctx.db, ctx.org_id, key)
    assert out is not None
    return out


ROUTER = Router(path="/api/v1", route_handlers=[routing_checks, regulator_pack, fact_sheet, fairness, sign_off])
