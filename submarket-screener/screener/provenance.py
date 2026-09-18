"""Every number in this project travels with its source and vintage.

Nothing in the pipeline is allowed to hand back a bare float. If a figure is
not available we return a Value with value=None and a populated
missing_reason, and that is what shows up in the workbook. We never fill a
gap with an estimate.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Value:
    """A single figure plus everything needed to defend it."""

    value: Any                 # float, int, str or None. None means missing.
    source: str = ""           # e.g. "Census ACS 5-Year API"
    vintage: str = ""          # e.g. "ACS 2020-2024 5-year"
    url: str = ""              # the exact endpoint or file the figure came from
    retrieved_at: str = ""     # ISO date the bytes were downloaded
    notes: str = ""            # caveats a reader needs
    missing_reason: str = ""   # must be non-empty when value is None

    def __post_init__(self) -> None:
        if self.value is None and not self.missing_reason:
            self.missing_reason = "not reported"

    @property
    def is_missing(self) -> bool:
        return self.value is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def missing(reason: str, *, source: str = "", vintage: str = "", url: str = "") -> Value:
    """Shorthand for a figure we could not obtain. Use this, never a zero."""
    return Value(None, source=source, vintage=vintage, url=url, missing_reason=reason)


@dataclass
class MetricSpec:
    """Describes a column: what it is, which way is good, and how it is scored."""

    key: str
    label: str
    pillar: str                 # demand | rent | supply | location | municipal
    higher_is_better: bool
    unit: str = ""              # "%", "$", "units", "miles", "index"
    decimals: int = 1
    scored: bool = True         # False for context-only columns
    description: str = ""


@dataclass
class Unit:
    """One candidate submarket."""

    geoid: str                  # Census GEOID: state+place (7) or state+county+cousub (10)
    name: str
    geo_type: str               # "place" or "county_subdivision"
    state_fips: str
    county_fips: str = ""       # 5-digit state+county
    county_name: str = ""
    lat: float | None = None
    lon: float | None = None
    land_area_sqmi: float | None = None
    # ZCTA overlaps, as (zcta5, weight) where weights sum to 1.0 across the unit.
    zctas: list[tuple[str, float]] = field(default_factory=list)

    @property
    def state_place_or_cousub(self) -> str:
        return self.geoid
