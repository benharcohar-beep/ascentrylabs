"""Which county is a Census place in?

Places do not carry a county in their GEOID (a place can straddle several
counties), but we need a county for every submarket because the jobs data
(QCEW, LAUS) and the FMR cross-check are published at county level.

The Census publishes national place-to-county reference files, but the exact
path and layout have moved between decennial vintages. Rather than hardcode
one guess, we try a list of candidates and parse whichever one answers,
detecting the delimiter and the columns by name. If none answer we say so
loudly and every county-level figure becomes MISSING. We never guess a county.

# LIMITATIONS
- A place that straddles several counties is assigned to its FIRST listed
  county, which is the one the Census lists first, not necessarily the one
  holding most of its population. The assignment is recorded in the workbook
  so it can be checked.
- This file is only needed for place-based markets (Lexington, Savannah). The
  Midwest markets use county subdivisions, whose GEOID already contains the
  county.
"""
from __future__ import annotations

import csv
import io

from ..cache import FetchError
from ..context import Context

SOURCE_NAME = "Census place-to-county reference file"

# Tried in order. Comment says what each is believed to contain. If all fail,
# the error message tells the user exactly where to look.
CANDIDATE_URLS = [
    # 2020 vintage national place file: pipe delimited, one row per
    # place/county part, with county FIPS and county name.
    "https://www2.census.gov/geo/docs/reference/codes2020/place/national_place2020.txt",
    "https://www2.census.gov/geo/docs/reference/codes2020/national_place2020.txt",
    # 2010 vintage equivalent, still published.
    "https://www2.census.gov/geo/docs/reference/codes/files/national_places.txt",
    "https://www2.census.gov/geo/docs/reference/codes2010/national_places.txt",
]

MANUAL_PATH_HINT = (
    "If every candidate URL 404s, browse "
    "https://www2.census.gov/geo/docs/reference/codes2020/ , download the "
    "national place file, and save it as data/cache/manual/place_county.txt "
    "(pipe or comma delimited, with state FIPS, place FIPS and county FIPS "
    "columns). The screener picks it up automatically."
)


def _sniff(text: str) -> str:
    head = text.splitlines()[0] if text else ""
    for delim in ("|", ",", "\t"):
        if head.count(delim) >= 3:
            return delim
    return ","


def _norm(name: str) -> str:
    return name.strip().upper().replace("﻿", "")


def _parse(text: str) -> dict[str, tuple[str, str]]:
    """Return {7-char place GEOID: (5-char county FIPS, county name)}."""
    delim = _sniff(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if not reader.fieldnames:
        raise FetchError("place-to-county file has no header row")

    cols = {_norm(f): f for f in reader.fieldnames}

    def find(*fragments: str) -> str | None:
        for norm_name, original in cols.items():
            if all(frag in norm_name for frag in fragments):
                return original
        return None

    state_col = find("STATEFP") or find("STATE", "FP") or find("STATEFIPS")
    place_col = find("PLACEFP") or find("PLACE", "FP")
    county_fp_col = find("COUNTYFP") or find("COUNTY", "FP")
    county_name_col = find("COUNTYNAME") or find("COUNTY", "NAME")

    if not (state_col and place_col and county_fp_col):
        raise FetchError(
            "place-to-county file does not have recognisable state, place and "
            f"county FIPS columns. Saw: {sorted(cols)}"
        )

    mapping: dict[str, tuple[str, str]] = {}
    for row in reader:
        state = (row.get(state_col) or "").strip().zfill(2)
        place = (row.get(place_col) or "").strip().zfill(5)
        county = (row.get(county_fp_col) or "").strip().zfill(3)
        if not state.isdigit() or not place.isdigit() or not county.isdigit():
            continue
        geoid = state + place
        # First listed county wins. Recorded as a limitation.
        if geoid not in mapping:
            name = (row.get(county_name_col) or "").strip() if county_name_col else ""
            mapping[geoid] = (state + county, name)
    if not mapping:
        raise FetchError("place-to-county file parsed but produced no rows")
    return mapping


def load(ctx: Context) -> tuple[dict[str, tuple[str, str]], dict]:
    """Return the mapping plus a provenance dict. Raises FetchError if unavailable."""
    manual = ctx.cache.root / "manual" / "place_county.txt"
    if manual.exists():
        mapping = _parse(manual.read_text(encoding="latin-1"))
        ctx.log(f"place-to-county: manual file, {len(mapping):,} places")
        return mapping, {
            "source": SOURCE_NAME + " (manual drop)",
            "vintage": "as downloaded by the user",
            "url": str(manual),
            "retrieved_at": "",
        }

    errors = []
    for url in CANDIDATE_URLS:
        try:
            resp = ctx.cache.get(url, key=f"place_county_{url.rsplit('/', 1)[-1]}", ttl_days=365)
            mapping = _parse(resp.body.decode("latin-1", errors="replace"))
            ctx.log(f"place-to-county: {url.rsplit('/', 1)[-1]}, {len(mapping):,} places")
            return mapping, {
                "source": SOURCE_NAME,
                "vintage": url.rsplit("/", 1)[-1],
                "url": url,
                "retrieved_at": resp.retrieved_at,
            }
        except FetchError as exc:
            errors.append(f"{url}: {exc}")

    raise FetchError(
        "Could not obtain a place-to-county crosswalk.\n  "
        + "\n  ".join(errors)
        + "\n"
        + MANUAL_PATH_HINT
    )
