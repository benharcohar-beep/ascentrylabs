"""Configuration loading.

Two kinds of config, both plain YAML you can edit without touching Python:

  config/weights.yml          the scoring weights and scoring options
  config/markets/<key>.yml    one file per market: counties, geography type,
                              employment centres, candidate selection rules
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
MARKETS_DIR = CONFIG_DIR / "markets"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
OUTPUT_DIR = PROJECT_ROOT / "output"


@dataclass
class EmploymentCenter:
    name: str
    lat: float
    lon: float
    note: str = ""


@dataclass
class MarketConfig:
    key: str
    name: str
    short_name: str
    states: list[str]
    counties: list[dict[str, str]]          # {fips, name, state}
    geo_type: str                            # place | county_subdivision
    geo_type_reason: str
    employment_centers: list[EmploymentCenter]
    trade_area_note: str = ""
    min_population: int = 2500
    max_distance_miles: float = 35.0
    target_submarkets: int = 10
    always_include: list[str] = field(default_factory=list)   # GEOIDs
    always_exclude: list[str] = field(default_factory=list)   # GEOIDs
    notes: str = ""

    @property
    def county_fips(self) -> list[str]:
        return [c["fips"] for c in self.counties]

    @property
    def core_county_fips(self) -> str:
        return self.counties[0]["fips"]

    def county_name(self, fips: str) -> str:
        for c in self.counties:
            if c["fips"] == fips:
                return c["name"]
        return ""


@dataclass
class Weights:
    pillars: dict[str, float]
    metrics: dict[str, float]
    scoring_method: str = "percentile"       # percentile | zscore
    winsorize_pct: float = 0.0
    attitude_scores: dict[str, float] = field(default_factory=dict)
    min_metrics_per_pillar: int = 1

    def normalised_pillars(self) -> dict[str, float]:
        total = sum(self.pillars.values())
        if total <= 0:
            raise ValueError("Pillar weights must sum to something greater than zero.")
        return {k: v / total for k, v in self.pillars.items()}


def load_weights(path: Path | None = None) -> Weights:
    path = path or CONFIG_DIR / "weights.yml"
    raw = yaml.safe_load(path.read_text())
    return Weights(
        pillars=raw["pillars"],
        metrics=raw.get("metrics", {}),
        scoring_method=raw.get("scoring_method", "percentile"),
        winsorize_pct=float(raw.get("winsorize_pct", 0.0)),
        attitude_scores=raw.get("attitude_scores", {}),
        min_metrics_per_pillar=int(raw.get("min_metrics_per_pillar", 1)),
    )


def load_market(key: str, path: Path | None = None) -> MarketConfig:
    path = path or MARKETS_DIR / f"{key}.yml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in MARKETS_DIR.glob("*.yml")))
        raise FileNotFoundError(f"No market config '{key}'. Available: {available}")
    raw: dict[str, Any] = yaml.safe_load(path.read_text())
    centers = [EmploymentCenter(**c) for c in raw.get("employment_centers", [])]
    return MarketConfig(
        key=raw["key"],
        name=raw["name"],
        short_name=raw.get("short_name", raw["name"]),
        states=[str(s).zfill(2) for s in raw["states"]],
        counties=[
            {"fips": str(c["fips"]).zfill(5), "name": c["name"], "state": str(c["fips"]).zfill(5)[:2]}
            for c in raw["counties"]
        ],
        geo_type=raw["geo_type"],
        geo_type_reason=raw.get("geo_type_reason", ""),
        employment_centers=centers,
        trade_area_note=raw.get("trade_area_note", ""),
        min_population=int(raw.get("min_population", 2500)),
        max_distance_miles=float(raw.get("max_distance_miles", 35.0)),
        target_submarkets=int(raw.get("target_submarkets", 10)),
        always_include=[str(g) for g in raw.get("always_include", [])],
        always_exclude=[str(g) for g in raw.get("always_exclude", [])],
        notes=raw.get("notes", ""),
    )


def list_markets() -> list[str]:
    return sorted(p.stem for p in MARKETS_DIR.glob("*.yml"))
