"""Distance from each submarket to the nearest employment centre.

Two modes:

  straight-line   great-circle miles between the submarket's population-weighted
                  centroid (from the Census Gazetteer) and the employment
                  centre. Always available, offline, no key, no rate limit.

  drive           road distance and time from the public OSRM demo server.
                  Optional, opt in with --osrm. The demo server is a courtesy
                  service with no uptime guarantee and a request rate limit, so
                  this is an enrichment and never a dependency. Results are
                  cached like everything else.

# LIMITATIONS
- A centroid is not a site. Two sites in the same municipality can be eight
  miles apart. This figure ranks municipalities, it does not underwrite a site.
- Straight-line distance understates travel in markets cut by water or a
  single river crossing. Savannah is the obvious case here.
- The employment centres are operator-set points listed in each market YAML,
  not derived from data. They are an input to the model, not an output of it.
- OSRM drive distance uses the free OpenStreetMap road network with default car
  routing. It has no traffic model, so it is a free-flow figure, not a rush
  hour commute.
"""
from __future__ import annotations

import json
import math

from ..cache import FetchError
from ..context import Context
from ..provenance import MetricSpec, Unit, Value, missing

SOURCE_NAME = "Great-circle distance (Census Gazetteer centroids)"
OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"
EARTH_RADIUS_MILES = 3958.7613

METRICS = [
    MetricSpec(
        key="miles_to_employment",
        label="Miles to nearest employment centre",
        pillar="location",
        higher_is_better=False,
        unit="miles",
        decimals=1,
        description=(
            "Great-circle miles from the submarket centroid to the nearest "
            "employment centre listed in the market config."
        ),
    ),
]

CONTEXT_COLUMNS = [
    MetricSpec("nearest_employment_center", "Nearest employment centre", "location",
               True, "", 0, scored=False),
    MetricSpec("drive_miles_to_employment", "Drive miles to employment centre", "location",
               False, "miles", 1, scored=False),
    MetricSpec("drive_minutes_to_employment", "Drive minutes to employment centre", "location",
               False, "min", 0, scored=False),
]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def _osrm_leg(ctx: Context, unit: Unit, center) -> tuple[float, float] | None:
    """Road miles and minutes, or None if the routing service did not answer."""
    # OSRM wants lon,lat order. Getting this the wrong way round is the classic
    # bug here and it fails silently by returning a route across the country.
    coords = f"{unit.lon},{unit.lat};{center.lon},{center.lat}"
    url = f"{OSRM_BASE}/{coords}"
    try:
        resp = ctx.cache.get(
            url,
            key=f"osrm_{unit.geoid}_{center.name}",
            params={"overview": "false"},
            ttl_days=365,
        )
        payload = json.loads(resp.text)
    except (FetchError, json.JSONDecodeError) as exc:
        ctx.log(f"OSRM lookup failed for {unit.name}: {exc}")
        return None
    if payload.get("code") != "Ok" or not payload.get("routes"):
        return None
    route = payload["routes"][0]
    return route["distance"] / 1609.344, route["duration"] / 60.0


def collect(ctx: Context, units: list[Unit]) -> dict[str, dict[str, Value]]:
    centers = ctx.market.employment_centers
    out: dict[str, dict[str, Value]] = {}

    if not centers:
        reason = "no employment centres configured for this market"
        for unit in units:
            out[unit.geoid] = {"miles_to_employment": missing(reason)}
        return out

    center_note = "; ".join(f"{c.name}: {c.note}" for c in centers if c.note)

    for unit in units:
        row: dict[str, Value] = {}
        if unit.lat is None or unit.lon is None:
            row["miles_to_employment"] = missing(
                "no centroid for this submarket in the Census Gazetteer"
            )
            out[unit.geoid] = row
            continue

        legs = [
            (haversine_miles(unit.lat, unit.lon, c.lat, c.lon), c) for c in centers
        ]
        best_miles, best_center = min(legs, key=lambda pair: pair[0])

        row["miles_to_employment"] = Value(
            round(best_miles, 2),
            source=SOURCE_NAME,
            vintage="Census Gazetteer centroid, employment centre set by operator",
            url="https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html",
            retrieved_at="",
            notes=(
                "Straight-line distance from the submarket's internal point to the "
                "nearest configured employment centre. Not a drive time. "
                + center_note
            ),
        )
        row["nearest_employment_center"] = Value(
            best_center.name,
            source=SOURCE_NAME,
            vintage="operator-set",
            notes=best_center.note,
        )

        if ctx.use_osrm:
            leg = _osrm_leg(ctx, unit, best_center)
            if leg is None:
                row["drive_miles_to_employment"] = missing(
                    "OSRM public demo server did not return a route"
                )
                row["drive_minutes_to_employment"] = missing(
                    "OSRM public demo server did not return a route"
                )
            else:
                miles, minutes = leg
                note = (
                    "OpenStreetMap car routing, free-flow, no traffic model. "
                    "Public demo server, best effort."
                )
                row["drive_miles_to_employment"] = Value(
                    round(miles, 1), source="OSRM public demo server",
                    vintage="current OSM road network", url=OSRM_BASE, notes=note,
                )
                row["drive_minutes_to_employment"] = Value(
                    round(minutes, 0), source="OSRM public demo server",
                    vintage="current OSM road network", url=OSRM_BASE, notes=note,
                )

        out[unit.geoid] = row
    return out
