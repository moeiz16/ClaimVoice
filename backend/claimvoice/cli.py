"""`claimvoice` command line: migrate, seed, reset (make migrate | seed | reset)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from claimvoice import clock
from claimvoice.config import get_settings

app = typer.Typer(add_completion=False, no_args_is_help=True)
BACKEND = Path(__file__).resolve().parents[1]


def _alembic_upgrade() -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")


@app.command()
def migrate() -> None:
    """Apply database migrations."""
    get_settings().data_dir.mkdir(parents=True, exist_ok=True)
    _alembic_upgrade()
    typer.echo("migrations applied")


@app.command()
def seed() -> None:
    """Seed Larkspur Mutual (idempotent; dated by CLAIMVOICE_DEMO_TODAY)."""
    from claimvoice.seed import run

    clock.install_from_settings(fresh=True)
    counts = asyncio.run(run())
    typer.echo("seeded " + ", ".join(f"{k}={v}" for k, v in counts.items()) + f" (today {clock.today()})")


@app.command()
def reset(yes: bool = typer.Option(False, "--yes", help="Confirm deleting the local database.")) -> None:
    """Delete the local SQLite database, then migrate and seed."""
    settings = get_settings()
    if not settings.is_sqlite:
        raise typer.BadParameter("reset only deletes local SQLite databases")
    if not yes:
        raise typer.BadParameter("pass --yes to delete the local database")
    path = Path(settings.database_url.split("///", 1)[1])
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)
    (settings.data_dir / "demo-clock.json").unlink(missing_ok=True)
    migrate()
    seed()


if __name__ == "__main__":
    app()
