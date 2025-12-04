"""Imports every table module so `Base.metadata` is complete (Alembic, tests, the seed)."""

from __future__ import annotations

from claimvoice.calls import models as calls_models
from claimvoice.claims import models as claims_models
from claimvoice.platform import models as platform_models
from claimvoice.policies import models as policies_models
from claimvoice.settings import models as settings_models

__all__ = ["calls_models", "claims_models", "platform_models", "policies_models", "settings_models"]
