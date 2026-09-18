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
# Verified against the live server on 2026-09-18, not guessed. The first
# answers with 2.5MB and this header:
#
#   STATE|STATEFP|PLACEFP|PLACENS|PLACENAME|TYPE|CLASSFP|FUNCSTAT|COUNTIES
#   GA|13|00184|02403056|Abbeville city|INCORPORATED PLACE|C1|A|Wilcox County
#
# Note COUNTIES, not a county FIPS. The file names the county and never
# numbers it, which is what defeated the first version of this reader: it
# looked for a county FIPS column, found none, and gave up, so every place
# based market lost every county level figure.
CANDIDATE_URLS = [
    "https://www2.census.gov/geo/docs/reference/codes2020/national_place2020.txt",
    # 2010 vintage. Same shape, column called COUNTY, blank lines between rows.
    "https://www2.census.gov/geo/docs/reference/codes/files/national_places.txt",
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


def _parse(text: str, county_fips_by_name: dict[str, str] | None = None
           ) -> dict[str, tuple[str, str]]:
    """Return {7-char place GEOID: (5-char county FIPS, county name)}.

    Census names the county rather than numbering it, so a name to FIPS map is
    needed. It comes from the market config, which already lists every county
    with both, so there is no second file to fetch and nothing else to 404.
    A place in a county the market does not cover resolves to no FIPS, which is
    correct: it is about to be filtered out anyway.
    """
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

    # COUNTIES in the 2020 file, COUNTY in the 2010 one. Both hold names.
    county_name_col = county_name_col or find("COUNTIES") or find("COUNTY")

    if not (state_col and place_col and (county_fp_col or county_name_col)):
        raise FetchError(
            "place-to-county file does not have recognisable state, place and "
            f"county columns. Saw: {sorted(cols)}"
        )

    by_name = {_norm(k): v for k, v in (county_fips_by_name or {}).items()}

    mapping: dict[str, tuple[str, str]] = {}
    for row in reader:
        state = (row.get(state_col) or "").strip().zfill(2)
        place = (row.get(place_col) or "").strip().zfill(5)
        if not state.isdigit() or not place.isdigit():
            continue
        geoid = state + place
        if geoid in mapping:
            continue

        names = [n.strip() for n in
                 (row.get(county_name_col) or "").split(",") if n.strip()]

        county_fips = ""
        county_name = names[0] if names else ""
        if county_fp_col:
            raw = (row.get(county_fp_col) or "").strip().zfill(3)
            if raw.isdigit():
                county_fips = state + raw
        if not county_fips and names:
            # Prefer a county the market actually covers. A place straddling a
            # covered and an uncovered county belongs in the screen, and taking
            # whichever Census listed first would drop it at the county filter
            # for no reason the reader could see.
            for candidate in names:
                hit = by_name.get(_norm(candidate))
                if hit:
                    county_fips, county_name = hit, candidate
                    break
        if county_fips:
            mapping[geoid] = (county_fips, county_name)
    if not mapping:
        raise FetchError(
            "place-to-county file parsed but matched no county. The file names "
            "counties rather than numbering them, so this usually means the "
            "market's configured county names do not match the Census spelling."
        )
    return mapping


def load(ctx: Context) -> tuple[dict[str, tuple[str, str]], dict]:
    """Return the mapping plus a provenance dict. Raises FetchError if unavailable."""
    # The market already lists every county it covers with both name and FIPS,
    # so the name to FIPS resolution needs no second download.
    county_fips_by_name = {
        county["name"]: county["fips"] for county in ctx.market.counties
        if county.get("name") and county.get("fips")
    }

    manual = ctx.cache.root / "manual" / "place_county.txt"
    if manual.exists():
        mapping = _parse(manual.read_text(encoding="latin-1"), county_fips_by_name)
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
            mapping = _parse(resp.body.decode("latin-1", errors="replace"),
                             county_fips_by_name)
            ctx.log(f"place-to-county: {url.rsplit('/', 1)[-1]}, {len(mapping):,} "
                    f"places matched to the {len(county_fips_by_name)} counties "
                    f"this market covers")
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
