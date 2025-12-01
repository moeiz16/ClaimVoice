"""Shared wire types."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import msgspec

Lang = Literal["en", "fr"]


class Model(msgspec.Struct, rename="camel", kw_only=True):
    """Base for every wire struct: camelCase keys, keyword-only construction."""


class Page[T](Model):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class Labeled(Model):
    """A code with its plain-words label (already in the viewer's language)."""

    key: str
    label: str


class PersonRef(Model):
    id: str
    name: str


class FieldError(Model):
    field: str
    message: str


class Problem(Model):
    """RFC 7807 body (application/problem+json)."""

    type: str
    title: str
    status: int
    code: str
    detail: str | None = None
    errors: list[FieldError] | None = None
    request_id: str | None = None


class TextSpan(Model):
    """Where a claim-file value was heard: a turn and character offsets into its (redacted) text."""

    turn_id: str
    start: int
    end: int


class Money(Model):
    amount: float
    currency: Literal["CAD", "USD"]


class ClockInfo(Model):
    today: str  # YYYY-MM-DD in the org's zone
    now: datetime
    demo: bool
    timezone: str
