"""Census Gazetteer files: the geographic spine of the screen.

These give us, for every place and every county subdivision in the country,
the GEOID, the name, the land area and an internal point (a latitude and
longitude guaranteed to fall inside the polygon). We use them to:

  1. build the candidate universe of submarkets for a market
  2. attach a centroid so we can measure distance to employment
  3. attach land area so density is available as context

# LIMITATIONS
- The internal point is a geometric point inside the boundary, not a
  population-weighted centroid. For a long thin township it can sit somewhere
  nobody lives.
- Boundaries change. A municipality that annexed land between the Gazetteer
  vintage and the ACS vintage will have slightly inconsistent geography across
  the two sources. For the Midwest markets in this screen the effect is small,
  but it is real and it is why the workbook records the vintage of each file.
- The Gazetteer is published for a specific year. We probe backwards for the
  most recent one available rather than hardcoding a year that will rot.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date

from ..cache import FetchError
from ..context import Context
from ..provenance import Unit
from . import census_place_county

SOURCE_NAME = "Census Gazetteer Files"
BASE = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer"

# Which Gazetteer product to read for each geography type this screen supports.
_PRODUCT = {
    "place": "place",
    "county_subdivision": "cousubs",
    "zcta": "zcta",
}

# Columns we need. The published header has trailing spaces on some names,
# which is why every lookup goes through _norm().
_NEEDED = ["USPS", "GEOID", "NAME", "ALAND_SQMI", "INTPTLAT", "INTPTLONG"]


def _norm(name: str) -> str:
    return name.strip().upper().replace("﻿", "")


def _decode(raw: bytes) -> str:
    # Gazetteer files are usually latin-1. Try UTF-8 first so accented place
    # names survive when the file is in fact UTF-8.
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _read_gazetteer(ctx: Context, product: str, year: int) -> tuple[list[dict], str, str]:
    """Return (rows, url, retrieved_at) for one Gazetteer product and year."""
    url = f"{BASE}/{year}_Gazetteer/{year}_Gaz_{product}_national.zip"
    resp = ctx.cache.get(url, key=f"gazetteer_{product}_{year}", ttl_days=365)

    try:
        archive = zipfile.ZipFile(io.BytesIO(resp.body))
    except zipfile.BadZipFile as exc:
        raise FetchError(f"{url} did not download as a zip archive: {exc}") from exc

    names = [n for n in archive.namelist() if n.lower().endswith(".txt")]
    if not names:
        raise FetchError(f"{url} contained no .txt file; archive holds {archive.namelist()}")

    text = _decode(archive.read(names[0]))
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if reader.fieldnames is None:
        raise FetchError(f"{url} has no header row")

    header_map = {_norm(f): f for f in reader.fieldnames}
    missing_cols = [c for c in _NEEDED if c not in header_map]
    if missing_cols:
        raise FetchError(
            f"{url} is missing expected columns {missing_cols}. "
            f"Found: {sorted(header_map)}. The Gazetteer layout may have changed."
        )

    rows = []
    for raw_row in reader:
        rows.append({c: (raw_row.get(header_map[c]) or "").strip() for c in _NEEDED})
    return rows, url, resp.retrieved_at


def latest_gazetteer(ctx: Context, product: str, max_back: int = 4) -> tuple[list[dict], int, str, str]:
    """Probe backwards from last year for the newest Gazetteer vintage available."""
    errors = []
    start = date.today().year
    for year in range(start, start - max_back - 1, -1):
        try:
            rows, url, retrieved = _read_gazetteer(ctx, product, year)
            ctx.log(f"Gazetteer {product}: using {year} vintage ({len(rows):,} rows)")
            return rows, year, url, retrieved
        except FetchError as exc:
            errors.append(f"{year}: {exc}")
    raise FetchError(
        "No Gazetteer file found for product "
        f"'{product}' in the last {max_back + 1} years.\n  " + "\n  ".join(errors)
    )


def build_universe(ctx: Context) -> tuple[list[Unit], dict]:
    """All places or county subdivisions inside the market's counties.

    Returns the units plus a provenance dict describing the file used.
    """
    market = ctx.market
    product = _PRODUCT[market.geo_type]
    rows, year, url, retrieved = latest_gazetteer(ctx, product)

    wanted_counties = set(market.county_fips)
    wanted_states = set(market.states)

    # Places carry no county in their GEOID, so for place-based markets we need
    # a crosswalk before we can filter to the trade area or attach county jobs
    # data. If the crosswalk is unavailable we keep every place in the state and
    # let the distance filter do the work, but we mark the county as unknown so
    # the county-level metrics come through as MISSING rather than as the wrong
    # county's numbers.
    place_to_county: dict[str, tuple[str, str]] = {}
    place_county_provenance: dict = {}
    place_county_error = ""
    if market.geo_type == "place":
        try:
            place_to_county, place_county_provenance = census_place_county.load(ctx)
        except FetchError as exc:
            place_county_error = str(exc)
            ctx.log(
                "WARNING: no place-to-county crosswalk. County-level metrics "
                "(jobs, FMR) will be MISSING and the trade area falls back to "
                "the distance filter alone."
            )

    units: list[Unit] = []
    for row in rows:
        geoid = row["GEOID"]
        if market.geo_type == "county_subdivision":
            # GEOID is state(2) + county(3) + cousub(5)
            if len(geoid) != 10:
                continue
            state_fips, county_fips = geoid[:2], geoid[:5]
            if county_fips not in wanted_counties:
                continue
        else:
            # GEOID is state(2) + place(5)
            if len(geoid) != 7:
                continue
            state_fips = geoid[:2]
            if state_fips not in wanted_states:
                continue
            county_fips, _county_name = place_to_county.get(geoid, ("", ""))
            if place_to_county and county_fips not in wanted_counties:
                continue

        def _f(key: str) -> float | None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                return None

        units.append(
            Unit(
                geoid=geoid,
                name=row["NAME"],
                geo_type=market.geo_type,
                state_fips=state_fips,
                county_fips=county_fips,
                county_name=market.county_name(county_fips) if county_fips else "",
                lat=_f("INTPTLAT"),
                lon=_f("INTPTLONG"),
                land_area_sqmi=_f("ALAND_SQMI"),
            )
        )

    provenance = {
        "source": SOURCE_NAME,
        "vintage": f"{year} Gazetteer, {product}",
        "url": url,
        "retrieved_at": retrieved,
        "place_to_county": place_county_provenance,
        "place_to_county_error": place_county_error,
    }
    ctx.log(
        f"Universe: {len(units)} {market.geo_type.replace('_', ' ')}s "
        f"in {len(wanted_counties)} counties"
    )
    return units, provenance
