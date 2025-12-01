"""Weather and catastrophe lookup. Bundled snapshot by default (public alert feeds, see docs/DATA.md): used to confirm
a reported hail or storm loss and to detect a surge. Times in the snapshot are offsets from the demo day, so the
alerts line up with `clock.today()`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

SNAPSHOT = Path(__file__).parent / "data" / "weather_snapshot.json"


@dataclass(frozen=True, slots=True)
class WeatherAlert:
    alert_id: str
    kind: str  # "hail" | "flood" | "wind" | "winter_storm" | "extreme_cold" | "rainfall"
    region: str  # ISO 3166-2, e.g. "CA-AB"
    area_label: str  # "Calgary (northeast)"
    headline: str
    starts_at: datetime
    ends_at: datetime
    source: str
    lat: float
    lon: float
    radius_km: float


@runtime_checkable
class WeatherFeed(Protocol):
    name: str

    async def alerts(self, region: str, at: datetime) -> list[WeatherAlert]: ...

    async def events_near(
        self, lat: float, lon: float, at: datetime, *, radius_km: float = 25
    ) -> list[WeatherAlert]: ...


class BundledWeather:
    """Reads tools/data/weather_snapshot.json, anchored to the demo day."""

    name = "bundled-weather"

    def __init__(self, demo_day: date, path: Path = SNAPSHOT) -> None:
        doc = json.loads(path.read_text())
        self._alerts: list[WeatherAlert] = []
        for a in doc["alerts"]:
            tz = ZoneInfo(a["tz"])
            day = demo_day + timedelta(days=a["dayOffset"])
            start = datetime.combine(day, datetime.strptime(a["startLocal"], "%H:%M").time(), tz)
            self._alerts.append(
                WeatherAlert(
                    a["id"],
                    a["kind"],
                    a["region"],
                    a["areaLabel"],
                    a["headline"],
                    start,
                    start + timedelta(hours=a["durationHours"]),
                    doc["source"],
                    a["lat"],
                    a["lon"],
                    a["radiusKm"],
                )
            )

    async def alerts(self, region: str, at: datetime) -> list[WeatherAlert]:
        return [a for a in self._alerts if a.region == region and a.starts_at <= at <= a.ends_at]

    async def events_near(self, lat: float, lon: float, at: datetime, *, radius_km: float = 25) -> list[WeatherAlert]:
        from math import asin, cos, radians, sin, sqrt

        def km(a: WeatherAlert) -> float:
            dlat, dlon = radians(a.lat - lat), radians(a.lon - lon)
            h = sin(dlat / 2) ** 2 + cos(radians(lat)) * cos(radians(a.lat)) * sin(dlon / 2) ** 2
            return 6371 * 2 * asin(sqrt(h))

        window = timedelta(days=3)  # a loss reported up to 3 days after the event still matches it
        return [
            a
            for a in self._alerts
            if a.starts_at - window <= at <= a.ends_at + window and km(a) <= radius_km + a.radius_km
        ]
