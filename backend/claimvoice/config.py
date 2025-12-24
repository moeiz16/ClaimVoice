"""Settings, read once from the environment (and `.env` at the repo root). Secrets only ever come from here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "ClaimVoice"
    api_port: int = 8040
    web_origin: str = "http://localhost:3040"
    secret_key: str = Field(default="dev-only-change-me-claimvoice-0000000000000000", min_length=32)

    database_url: str = f"sqlite+aiosqlite:///{REPO_ROOT / 'data' / 'claimvoice.db'}"
    data_dir: Path = REPO_ROOT / "data"
    recordings_dir: Path = REPO_ROOT / "data" / "recordings"
    uploads_dir: Path = REPO_ROOT / "data" / "uploads"
    mlflow_tracking_uri: str = f"sqlite:///{REPO_ROOT / 'mlruns' / 'mlflow.db'}"

    # Demo clock (claimvoice/clock.py). "off" or empty means real time.
    claimvoice_demo_today: str | None = "2026-01-08"
    claimvoice_demo_time: str | None = None
    claimvoice_demo_tz: str = "America/Edmonton"

    # Sessions (real wall clock, never the demo clock)
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    cookie_secure: bool = False

    # Cloud adapters. Every one defaults to an offline, deterministic fake.
    llm_fake: bool = True
    llm_model: str = "groq/llama-3.1-8b-instant"
    stt_provider: Literal["fake", "groq", "deepgram"] = "fake"
    tts_provider: Literal["fake", "cartesia", "elevenlabs"] = "fake"
    sms_provider: Literal["fake"] = "fake"  # text messages go to a local outbox; no live sender yet
    weather_source: Literal["bundled"] = "bundled"  # the bundled alert snapshot
    groq_api_key: str | None = None
    deepgram_api_key: str | None = None
    cartesia_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    cartesia_voice_en: str = ""
    cartesia_voice_fr: str = ""
    elevenlabs_voice_en: str = ""
    elevenlabs_voice_fr: str = ""

    # Voice runtime
    voice_ice_servers: str = ""  # comma-separated STUN/TURN URLs; empty = host candidates only (local demo)
    voice_turn_budget_ms: int = 800
    voice_tool_budget_ms: int = 600

    @property
    def demo_today(self) -> str | None:
        value = (self.claimvoice_demo_today or "").strip()
        return None if value.lower() in {"", "off", "none", "real"} else value

    def llm_api_key(self, model: str) -> str | None:
        """The key for a LiteLLM model name (`groq/...`, `gemini/...`, `openrouter/...`), read from settings so a
        key kept only in `.env` reaches the provider too."""
        provider = model.split("/", 1)[0].lower()
        return {
            "groq": self.groq_api_key,
            "gemini": self.gemini_api_key,
            "openrouter": self.openrouter_api_key,
        }.get(provider)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
