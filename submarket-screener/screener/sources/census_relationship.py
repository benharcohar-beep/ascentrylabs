"""ZCTA to submarket crosswalk, weighted by land area of overlap.

Zillow publishes rent by ZIP. Our submarkets are municipalities. ZIPs and
municipalities do not line up, so we need a weighting. The Census publishes
2020 relationship files that give, for every pair of overlapping geographies,
the land area of the overlap itself. That is the honest way to do this: a ZIP
that is 80% inside a village contributes four times as much as one that is 20%
inside it.

# LIMITATIONS
- Land area of overlap is a proxy for where people live. A ZIP whose overlap
  with a village is mostly farmland gets more weight than it deserves. A
  population-weighted crosswalk would be better; the free option for that is
  the HUD USPS crosswalk, which is residential-address weighted but only
  publishes ZIP to county subdivision, not ZIP to place, so it does not cover
  the Lexington and Savannah markets. This screen uses one method for all four
  markets so the numbers are comparable.
- The relationship files are 2020 Census geography. Annexations since 2020 are
  not reflected.
- ZCTAs are not USPS ZIP codes. They are Census approximations built from
  blocks. Zillow keys its file on the postal ZIP. The two agree for the large
  majority of residential ZIPs but not all of them, and there is no free exact
  crosswalk. This is stated in the README.
"""
from __future__ import annotations

import csv
import io

from ..cache import FetchError
from ..context import Context
from ..provenance import Unit

SOURCE_NAME = "Census 2020 ZCTA relationship files"
BASE = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520"

_FILES = {
    "place": "tab20_zcta520_place20_natl.txt",
    "county_subdivision": "tab20_zcta520_cousub20_natl.txt",
}


def _norm(name: str) -> str:
    return name.strip().upper().replace("﻿", "")


def _find_column(cols: dict[str, str], *fragments: str) -> str | None:
    for norm_name, original in cols.items():
        if all(frag in norm_name for frag in fragments):
            return original
    return None


def attach_zctas(ctx: Context, units: list[Unit]) -> dict:
    """Populate unit.zctas in place. Returns a provenance dict."""
    geo_type = ctx.market.geo_type
    filename = _FILES[geo_type]
    url = f"{BASE}/{filename}"

    try:
        resp = ctx.cache.get(url, key=f"rel2020_{filename}", ttl_days=365)
    except FetchError as exc:
        ctx.log(
            f"WARNING: ZCTA crosswalk unavailable ({exc}). Rent metrics will be MISSING."
        )
        return {
            "source": SOURCE_NAME,
            "vintage": "2020 Census geography",
            "url": url,
            "retrieved_at": "",
            "error": str(exc),
        }

    text = resp.body.decode("latin-1", errors="replace")
    delim = "|" if text.splitlines()[0].count("|") >= 3 else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if not reader.fieldnames:
        raise FetchError(f"{url} has no header row")

    cols = {_norm(f): f for f in reader.fieldnames}
    zcta_col = _find_column(cols, "GEOID", "ZCTA")
    target_token = "PLACE" if geo_type == "place" else "COUSUB"
    target_col = _find_column(cols, "GEOID", target_token)
    # AREALAND_PART is the land area of the intersection of the two geographies.
    area_col = _find_column(cols, "AREALAND", "PART") or _find_column(cols, "ALAND", "PART")

    if not (zcta_col and target_col and area_col):
        raise FetchError(
            f"{url} does not have the expected GEOID and overlap-area columns. "
            f"Saw: {sorted(cols)}. Looked for a ZCTA GEOID, a {target_token} GEOID "
            f"and an AREALAND_PART column."
        )

    wanted = {u.geoid for u in units}
    # {unit geoid: {zcta: overlap land area}}
    overlaps: dict[str, dict[str, float]] = {g: {} for g in wanted}

    for row in reader:
        target = (row.get(target_col) or "").strip()
        if target not in overlaps:
            continue
        zcta = (row.get(zcta_col) or "").strip().zfill(5)
        if not zcta.isdigit():
            continue
        try:
            area = float(row.get(area_col) or 0.0)
        except ValueError:
            continue
        if area <= 0:
            # A zero-land-area overlap is a boundary touch, not a real overlap.
            continue
        overlaps[target][zcta] = overlaps[target].get(zcta, 0.0) + area

    attached = 0
    for unit in units:
        parts = overlaps.get(unit.geoid, {})
        total = sum(parts.values())
        if total <= 0:
            unit.zctas = []
            continue
        unit.zctas = sorted(
            ((z, a / total) for z, a in parts.items()),
            key=lambda pair: pair[1],
            reverse=True,
        )
        attached += 1

    ctx.log(f"ZCTA crosswalk: matched {attached} of {len(units)} submarkets")
    return {
        "source": SOURCE_NAME,
        "vintage": "2020 Census geography, land area of overlap weights",
        "url": url,
        "retrieved_at": resp.retrieved_at,
        "matched": attached,
        "total": len(units),
    }
