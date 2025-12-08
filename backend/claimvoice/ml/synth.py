"""Synthetic first-notice-of-loss records for training and testing the routing checks (docs/DATA.md).

Each record looks like what the line collects at hang-up: a claim file (the same slot keys the dialogue fills), the
policy facts the platform holds, and the call facts the engine reports. Features come from `build_features`, the
same function the scorer uses, so training and serving can't drift apart.

* **Claim cost** is drawn from freMTPL2's empirical claim amounts (real French motor claims, conditioned on vehicle
  age and power bands for motor losses), rescaled by loss type for property losses and moved by the facts that make
  a loss bigger (an injury, a car that can't be driven, a home open to the weather, water still coming in, rooms,
  a home that can't be lived in). Without the data files a lognormal with the same median and tail stands in, so
  tests run anywhere; `make train` always uses the real distribution.
* **"Large or complex"** (the size check's target) is the top fifth of cost for its line, or an injury with another
  party, or a home that can't be lived in.
* **Closer-look labels** come from documented fraud patterns injected independently of region, language and age,
  each at a stated rate, combined so no single sign decides; 3 % label noise mimics investigators disagreeing.

Region, language and age band are generated with realistic mixes and kept only for fairness testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from claimvoice.ml.features import build_features

REPO_ROOT = Path(__file__).resolve().parents[3]
FREMTPL_DIR = REPO_ROOT / "data" / "fremtpl2"
START = date(2023, 1, 1)
END = date(2025, 12, 31)

# Injected closer-look patterns: (key, rate, weight in the latent score). Documented in docs/DATA.md.
PATTERNS: dict[str, tuple[float, float]] = {
    "new_policy": (0.05, 2.7),  # loss within 30 days of the policy start
    "coverage_raised": (0.04, 2.29),  # coverage raised within 45 days before the loss
    "late_report": (0.05, 1.76),  # reported more than 14 days after the loss
    "story_changes": (0.04, 2.56),  # two or more corrections to date, place or sequence
    "weather_contradiction": (0.12, 2.84),  # storm damage where no event was recorded (wind/hail only)
    "theft_no_report": (0.20, 2.16),  # theft with no police report (theft only)
    "round_estimate": (0.03, 1.62),  # a round figure in the top band
    "third_party_pressure": (0.025, 3.24),  # a non-policyholder pushing for a fast payment
    "prior_cluster": (0.03, 1.76),  # three or more claims in 36 months
    "photos_declined": (0.06, 1.08),
}
# Signs that compound when they appear together (why a tree model can beat an additive scorecard).
INTERACTIONS: dict[frozenset[str], float] = {
    frozenset({"new_policy", "coverage_raised"}): 1.6,
    frozenset({"story_changes", "third_party_pressure"}): 1.4,
    frozenset({"late_report", "theft_no_report"}): 1.2,
    frozenset({"late_report", "photos_declined"}): 1.0,
}
FRAUD_INTERCEPT = -5.3
LABEL_NOISE = 0.03

# Loss mix by season and region (fairness: theft and collision shares are the same everywhere).
_MIX_WINTER = {
    "CA-AB": {"collision": 0.36, "wind": 0.22, "water": 0.20, "theft": 0.12, "fire": 0.06, "hail": 0.04},
    "US-CO": {"collision": 0.40, "wind": 0.14, "water": 0.20, "theft": 0.12, "fire": 0.06, "hail": 0.08},
    "CA-QC": {"collision": 0.36, "wind": 0.10, "water": 0.32, "theft": 0.12, "fire": 0.06, "hail": 0.04},
}
_MIX_SUMMER = {
    "CA-AB": {"collision": 0.36, "wind": 0.10, "water": 0.12, "theft": 0.12, "fire": 0.06, "hail": 0.24},
    "US-CO": {"collision": 0.38, "wind": 0.08, "water": 0.10, "theft": 0.12, "fire": 0.06, "hail": 0.26},
    "CA-QC": {"collision": 0.38, "wind": 0.12, "water": 0.22, "theft": 0.12, "fire": 0.06, "hail": 0.10},
}
_COST_SCALE = {"collision": 1.0, "wind": 1.5, "hail": 1.3, "water": 2.0, "fire": 3.6, "theft": 1.1}
_PARTS = {
    "collision": ["bumper", "trunk", "door", "fender", "hood", "headlight", "mirror"],
    "hail": ["roof", "skylight", "siding", "hood", "windshield"],
    "wind": ["shingles", "roof", "siding", "fence", "skylight", "window", "eavestrough"],
    "water": ["floor", "drywall", "carpet", "ceiling"],
    "fire": ["ceiling", "drywall", "floor"],
    "theft": ["door", "window"],
}


@dataclass
class CostModel:
    """Empirical claim amounts, by vehicle-age and power band, from freMTPL2 (or a lognormal stand-in)."""

    amounts: dict[tuple[int, int], np.ndarray]
    pooled: np.ndarray
    source: str

    def draw(self, rng: np.random.Generator, veh_age: float, veh_power: int) -> float:
        key = (min(int(veh_age // 5), 3), min(max(veh_power - 4, 0) // 3, 2))
        pool = self.amounts.get(key)
        if pool is None or len(pool) < 50:
            pool = self.pooled
        return float(pool[rng.integers(0, len(pool))])


def load_cost_model(directory: Path = FREMTPL_DIR) -> CostModel:
    freq_path, sev_path = directory / "freMTPL2freq.parquet", directory / "freMTPL2sev.parquet"
    if freq_path.exists() and sev_path.exists():
        freq = pd.read_parquet(freq_path, columns=["IDpol", "VehAge", "VehPower"])
        sev = pd.read_parquet(sev_path)
        freq["IDpol"] = freq["IDpol"].astype("int64")
        freq = freq.drop_duplicates("IDpol")
        sev["IDpol"] = sev["IDpol"].astype("int64")
        df = sev.merge(freq, on="IDpol", how="inner")
        df = df[(df["ClaimAmount"] > 50) & (df["ClaimAmount"] < 500_000)]
        df["age_b"] = np.minimum(df["VehAge"] // 5, 3).astype(int)
        df["pow_b"] = np.minimum(np.maximum(df["VehPower"] - 4, 0) // 3, 2).astype(int)
        amounts = {
            (int(a), int(p)): g["ClaimAmount"].to_numpy(dtype=float) for (a, p), g in df.groupby(["age_b", "pow_b"])
        }
        return CostModel(amounts, df["ClaimAmount"].to_numpy(dtype=float), "freMTPL2")
    rng = np.random.default_rng(11)
    pooled = np.exp(rng.normal(np.log(1200), 1.15, 20000))
    return CostModel({}, pooled, "lognormal stand-in")


def _season(d: date) -> str:
    return "winter" if d.month in (11, 12, 1, 2, 3) else "summer"


def _pick(rng: np.random.Generator, mix: dict[str, float]) -> str:
    keys = list(mix)
    p = np.array([mix[k] for k in keys])
    return str(keys[int(rng.choice(len(keys), p=p / p.sum()))])


def _monthly_weights(start: date, end: date) -> tuple[list[date], np.ndarray]:
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    # gentle growth of the book over time and more calls in winter
    w = np.array([1.0 + 0.25 * (d - start).days / 1000 + (0.25 if _season(d) == "winter" else 0.0) for d in days])
    return days, w / w.sum()


def generate(
    n: int = 12000,
    *,
    seed: int = 7,
    start: date = START,
    end: date = END,
    cost_model: CostModel | None = None,
    wind_surge: tuple[date, date] | None = None,
    shift: dict[str, float] | None = None,
) -> pd.DataFrame:
    """`n` synthetic claim calls with loss dates between `start` and `end`. `wind_surge` adds a Chinook-style wind
    surge in Calgary for those dates; `shift` multiplies pattern rates or cost (drift tests)."""
    rng = np.random.default_rng(seed)
    cm = cost_model or load_cost_model()
    shift = shift or {}
    days, weights = _monthly_weights(start, end)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        loss_day = days[int(rng.choice(len(days), p=weights))]
        region = str(rng.choice(["CA-AB", "US-CO", "CA-QC"], p=[0.5, 0.3, 0.2]))
        mix = dict((_MIX_WINTER if _season(loss_day) == "winter" else _MIX_SUMMER)[region])
        if wind_surge and wind_surge[0] <= loss_day <= wind_surge[1] and region == "CA-AB":
            mix["wind"] = mix["wind"] * 12
        if "wind_share" in shift:
            mix["wind"] = mix["wind"] * shift["wind_share"]
        loss_type = _pick(rng, mix)
        language = (
            "fr" if (region == "CA-QC" and rng.random() < 0.85) or (region != "CA-QC" and rng.random() < 0.02) else "en"
        )
        age_band = str(rng.choice(["under_35", "35_64", "65_plus"], p=[0.27, 0.53, 0.20]))
        line = (
            "auto"
            if loss_type == "collision" or (loss_type in ("theft", "hail") and rng.random() < 0.4)
            else ("property")
        )
        # ---- facts heard on the call
        cf: dict[str, Any] = {"loss_type": loss_type}
        severe = rng.random() < 0.12 * shift.get("severe", 1.0)  # a hidden "bad one": raises several facts together
        if loss_type == "collision":
            cf["other_party_involved"] = bool(rng.random() < 0.7)
            cf["injury_reported"] = bool(rng.random() < (0.28 if severe else 0.09))
            cf["vehicle_drivable"] = bool(rng.random() > (0.65 if severe else 0.18))
            cf["airbags_deployed"] = bool(not cf["vehicle_drivable"] and rng.random() < 0.45)
            cf["police_report_filed"] = bool(rng.random() < (0.7 if cf["other_party_involved"] else 0.25))
        else:
            cf["injury_reported"] = bool(rng.random() < (0.05 if loss_type == "fire" else 0.01))
        if loss_type in ("wind", "hail"):
            cf["roof_or_window_damage"] = bool(rng.random() < 0.7)
            cf["siding_or_fence_damage"] = bool(rng.random() < 0.5)
            cf["open_to_weather"] = bool(cf["roof_or_window_damage"] and rng.random() < (0.55 if severe else 0.15))
            cf["home_livable"] = bool(rng.random() > (0.25 if severe else 0.02))
        if loss_type == "water":
            cf["water_source"] = str(
                rng.choice(["burst_pipe", "sewer_backup", "overland", "appliance"], p=[0.45, 0.25, 0.1, 0.2])
            )
            cf["water_still_entering"] = bool(rng.random() < (0.55 if severe else 0.18))
            cf["rooms_affected"] = int(min(6, 1 + rng.poisson(2.2 if severe else 0.9)))
            cf["home_livable"] = bool(rng.random() > (0.35 if severe else 0.04))
        if loss_type == "fire":
            cf["rooms_affected"] = int(min(8, 1 + rng.poisson(2.8 if severe else 1.0)))
            cf["home_livable"] = bool(rng.random() > (0.7 if severe else 0.25))
            cf["fire_department_attended"] = bool(rng.random() < 0.75)
        if loss_type == "theft":
            cf["police_report_filed"] = bool(rng.random() < 0.85)
            cf["forced_entry"] = bool(rng.random() < 0.6)
        n_parts = int(min(len(_PARTS[loss_type]), 1 + rng.poisson(2.0 if severe else 0.8)))
        cf["damage_areas"] = ", ".join(rng.choice(_PARTS[loss_type], size=n_parts, replace=False))
        cf["loss_description"] = " ".join(["word"] * int(6 + rng.poisson(14)))
        hour = int(rng.integers(0, 24))
        cf["loss_time"] = f"{hour:02d}:{int(rng.integers(0, 60)):02d}"
        cf["loss_date"] = loss_day.isoformat()
        cf["photos_promised"] = True
        # ---- policy facts
        tenure_days = int(rng.exponential(365 * 6.5)) + 40
        prior = int(rng.poisson(0.35))
        coverage_changed: date | None = None
        if rng.random() < 0.08:
            coverage_changed = loss_day - timedelta(days=int(rng.integers(60, 900)))
        report_hours = float(np.exp(rng.normal(np.log(9), 1.1)))
        # ---- inject patterns (independently of region, language and age band)
        present: list[str] = []
        for key, (rate, _w) in PATTERNS.items():
            r = rate * shift.get(key, 1.0)
            if key == "weather_contradiction" and loss_type not in ("wind", "hail"):
                continue
            if key == "theft_no_report":
                if loss_type == "theft" and rng.random() < r:
                    cf["police_report_filed"] = False
                    present.append(key)
                continue
            if rng.random() < r:
                present.append(key)
        facts: dict[str, Any] = {"key_fact_corrections": int(rng.random() < 0.07)}
        for key in present:
            if key == "new_policy":
                tenure_days = int(rng.integers(3, 30))
            elif key == "coverage_raised":
                coverage_changed = loss_day - timedelta(days=int(rng.integers(2, 45)))
            elif key == "late_report":
                report_hours = float(rng.integers(15, 60)) * 24
            elif key == "story_changes":
                facts["key_fact_corrections"] = int(rng.integers(2, 4))
            elif key == "round_estimate":
                cf["caller_damage_estimate_band"] = "over_50k"
                facts["round_number_estimate"] = True
            elif key == "third_party_pressure":
                cf["caller_relationship"] = "other"
                facts["payment_pressure"] = True
            elif key == "prior_cluster":
                prior = int(rng.integers(3, 6))
            elif key == "photos_declined":
                cf["photos_promised"] = False
        weather_ok = loss_type in ("wind", "hail") and "weather_contradiction" not in present
        facts["weather_confirms_loss"] = weather_ok if loss_type in ("wind", "hail", "water") else None
        facts["surge_event_match"] = bool(
            wind_surge and wind_surge[0] <= loss_day <= wind_surge[1] and region == "CA-AB" and loss_type == "wind"
        )
        answered = datetime.combine(loss_day, datetime.min.time(), UTC) + timedelta(hours=hour + report_hours)
        facts["answered_at"] = answered.isoformat()
        # ---- cost (real freMTPL2 amounts, moved by the facts)
        veh_age = float(rng.integers(0, 16)) if line == "auto" else 0.0
        veh_power = int(rng.integers(4, 13))
        base = cm.draw(rng, veh_age, veh_power) * _COST_SCALE[loss_type] * shift.get("cost", 1.0)
        mult = 1.0
        mult *= 2.8 if cf.get("injury_reported") else 1.0
        mult *= 1.25 if cf.get("other_party_involved") else 1.0
        mult *= 1.9 if cf.get("vehicle_drivable") is False else 1.0
        mult *= 1.8 if cf.get("airbags_deployed") else 1.0
        mult *= 2.3 if cf.get("open_to_weather") else 1.0
        mult *= 1.7 if cf.get("water_still_entering") else 1.0
        mult *= 1 + 0.35 * (int(cf.get("rooms_affected") or 1) - 1)
        mult *= 2.2 if cf.get("home_livable") is False else 1.0
        mult *= 1 + 0.22 * (n_parts - 1)
        cost = base * mult * float(np.exp(rng.normal(0, 0.35)))
        if "caller_damage_estimate_band" not in cf and rng.random() < 0.35:
            noisy = cost * float(np.exp(rng.normal(0, 0.5)))
            cf["caller_damage_estimate_band"] = (
                "under_2k"
                if noisy < 2000
                else "2k_10k"
                if noisy < 10000
                else "10k_50k"
                if noisy < 50000
                else "over_50k"
            )
        # ---- closer-look label
        latent = FRAUD_INTERCEPT + sum(PATTERNS[k][1] for k in present) + float(rng.normal(0, 0.6))
        latent += sum(w for pair, w in INTERACTIONS.items() if pair <= set(present))
        if "late_report" in present and report_hours > 30 * 24:
            latent += 0.8  # very late reports weigh more than late ones
        fraud = int(rng.random() < 1 / (1 + np.exp(-latent)))
        if rng.random() < LABEL_NOISE:
            fraud = int(rng.random() < 0.05)
        policy = {
            "line": line,
            "status": "active",
            "effective_from": (loss_day - timedelta(days=tenure_days)).isoformat(),
            "effective_to": None,
            "coverage_changed_at": coverage_changed.isoformat() if coverage_changed else None,
            "deductible": float(rng.choice([250, 500, 1000, 1500, 2500], p=[0.15, 0.35, 0.3, 0.12, 0.08])),
            "coverage_limit": float(rng.choice([50_000, 400_000, 650_000, 1_000_000])),
            "prior_claims_36m": prior,
            "vehicle_age_years": veh_age,
        }
        feats = build_features(cf, policy, {"facts": facts})
        rows.append(
            {
                **feats,
                "claim_id": f"S{seed}-{i:05d}",
                "loss_date": pd.Timestamp(loss_day),
                "loss_type": loss_type,
                "line": line,
                "cost": round(cost, 2),
                "fraud": fraud,
                "patterns": ",".join(present),
                "region": region,
                "language": language,
                "age_band": age_band,
            }
        )
    df = pd.DataFrame(rows)
    df["cost_rank_in_line"] = df.groupby("line")["cost"].rank(pct=True)
    df["large"] = (
        (df["cost_rank_in_line"] >= 0.80)
        | ((df["injury_reported"] == 1) & (df["other_party_involved"] == 1))
        | (df["home_not_livable"] == 1)
    ).astype(int)
    return df.drop(columns=["cost_rank_in_line"])


def time_split(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Leakage-safe split by loss month: train before July 2025, validate July-September, test October-December."""
    train = df[df["loss_date"] < "2025-07-01"]
    valid = df[(df["loss_date"] >= "2025-07-01") & (df["loss_date"] < "2025-10-01")]
    test = df[df["loss_date"] >= "2025-10-01"]
    return {"train": train, "valid": valid, "test": test}
