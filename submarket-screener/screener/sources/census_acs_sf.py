"""ACS demand figures from the summary files, which need no API key.

The Census Data API has required a key on every request since 12 May 2026.
The same estimates are also published as the "table-based summary file": one
pipe-delimited national file per table, on www2.census.gov, open to anyone.
This module reads those files and hands back exactly the structure the API
route hands back, so census_acs.compute_metrics does the arithmetic once and
both routes cannot drift apart.

Everything here was written against the output of tools/probe_acs_summary_file.py
run on a machine that can reach Census, not against an assumption:

    https://www2.census.gov/programs-surveys/acs/summary_file/2024/
        table-based-SF/data/5YRData/acsdt5y2024-b01003.dat

    GEO_ID|B01003_E001|B01003_M001
    0600000US5500100275|2050|265
    1600000US5500100|2024|276

Two things that fell out of the probe and shape the whole module:

1. GEO_ID carries the FIPS code, so the separate 92MB geography file is not
   needed. "0600000US" + state + county + cousub for a county subdivision,
   "1600000US" + state + place for a place. Strip the prefix and the remainder
   is byte for byte the GEOID the rest of this tool already uses.

2. The files are national and some are large: 18MB for total population, 200MB
   for the age table. A market needs one state. So they are streamed and
   filtered to the state prefix, and only the filtered extract is cached. See
   Cache.get_filtered_lines.

# LIMITATIONS
- Same estimates, same margins of error and same sentinels as the API. The
  numbers are not "close to" the API's, they are the same release.
- Column naming differs: the file writes B01003_E001 and B01003_M001 where the
  API writes B01003_001E and B01003_001M. Translated on the way in, so the
  computation only ever sees API spelling.
- Only summary levels 060 (county subdivision) and 160 (place) are read, which
  are the two geographies this screen uses.
- The vintage is found by probing, because a release appears here at a
  different moment from the API.
- Downloads are much larger than the API's few kilobytes. That is the price of
  not needing a credential, and it is paid once because the extract is cached.
"""
from __future__ import annotations

from ..cache import FetchError
from ..provenance import Unit

SOURCE_NAME = "Census ACS 5-Year Estimates summary file"
BASE = "https://www2.census.gov/programs-surveys/acs/summary_file"
DATA_URL = "{base}/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{table}.dat"

# Summary level prefixes, from the probe. The digits after the level are
# component and "US", fixed for these two.
SUMLEVEL_PREFIX = {
    "county_subdivision": "0600000US",
    "place": "1600000US",
}

# Which table each variable lives in. The API takes any mix of variables in one
# call; here each table is a separate file, so the module has to know.
TABLE_OF = {
    "B01003": "b01003",   # total population
    "B11001": "b11001",   # households
    "B25003": "b25003",   # tenure, for renter share
    "B19013": "b19013",   # median household income
    "B01002": "b01002",   # median age
    "B25064": "b25064",   # median gross rent
    "B01001": "b01001",   # sex by age, for the 20 to 34 share
}

# The age table is 200MB before filtering. It is worth 10 of the 108 points
# inside the demand pillar, so it is fetched last and its failure is survivable:
# every other demand column is already in hand by then.
LARGE_TABLES = {"b01001"}

# Probing starts here and walks back. The summary file for a release appears
# later than the API's, so the newest year is not knowable in advance.
PROBE_FROM_OFFSET = 1
PROBE_YEARS_BACK = 4


def _api_name(file_column: str) -> str:
    """B01003_E001 -> B01003_001E, which is what the computation reads.

    The two halves of Census publish the same variable under two spellings.
    Translating here rather than in the computation keeps the API route's
    naming as the single one the maths is written against.
    """
    table, _, rest = file_column.partition("_")
    if not rest or len(rest) < 2:
        return file_column
    kind, number = rest[0], rest[1:]
    if kind not in ("E", "M"):
        return file_column
    return f"{table}_{number}{kind}"


def _state_prefixes(ctx, units: list[Unit]) -> tuple[str, ...]:
    """The GEO_ID prefixes that select every state this market touches."""
    prefix = SUMLEVEL_PREFIX.get(ctx.market.geo_type)
    if prefix is None:
        raise FetchError(
            f"the summary file reader does not handle geo_type "
            f"{ctx.market.geo_type!r}. It reads county subdivisions and places, "
            f"which are the two this screen uses."
        )
    states = sorted({u.geoid[:2] for u in units} or set(ctx.market.states))
    return tuple(f"{prefix}{state}" for state in states)


def _geoid_from(geo_id: str) -> str:
    """Strip the summary level prefix, leaving the GEOID this tool uses."""
    _, _, rest = geo_id.partition("US")
    return rest


def _read_table(ctx, year: int, table: str, prefixes: tuple[str, ...],
                ) -> tuple[dict[str, dict[str, str]], str, str]:
    """One table, one year, filtered to the states in play."""
    url = DATA_URL.format(base=BASE, year=year, table=table)
    resp = ctx.cache.get_filtered_lines(
        url,
        key=f"acs_sf_{year}_{table}_{'_'.join(p[-2:] for p in prefixes)}",
        prefixes=prefixes,
        ttl_days=180,
    )
    text = resp.text.lstrip("﻿")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise FetchError(f"{url} produced an empty extract.")

    header = lines[0].split("|")
    if header[0] != "GEO_ID":
        raise FetchError(
            f"{url}: expected the first column to be GEO_ID, found {header[0]!r}. "
            f"Header: {header[:8]}"
        )
    names = [_api_name(c) for c in header]

    out: dict[str, dict[str, str]] = {}
    for line in lines[1:]:
        parts = line.split("|")
        if len(parts) != len(header):
            # A short row means the file layout moved. Reporting MISSING for
            # this state is right; silently zipping mismatched columns is how
            # a margin of error ends up read as an estimate.
            raise FetchError(
                f"{url}: row has {len(parts)} fields against {len(header)} "
                f"columns in the header. First field: {parts[0]!r}"
            )
        geoid = _geoid_from(parts[0])
        if not geoid:
            continue
        out[geoid] = dict(zip(names[1:], parts[1:]))
    return out, url, resp.retrieved_at


def _probe_year(ctx, prefixes: tuple[str, ...]) -> int:
    """Newest year whose summary file answers, using the smallest table."""
    from datetime import date
    start = date.today().year - PROBE_FROM_OFFSET
    errors = []
    for year in range(start, start - PROBE_YEARS_BACK - 1, -1):
        try:
            rows, _, _ = _read_table(ctx, year, "b01003", prefixes)
        except FetchError as exc:
            errors.append(f"{year}: {exc}")
            continue
        if rows:
            ctx.log(f"ACS summary file: newest available vintage is {year} 5-year "
                    f"({len(rows):,} geographies in the states requested)")
            return year
        errors.append(f"{year}: the file answered but held no row for these states")
    raise FetchError(
        "No ACS 5-year summary file answered for the last "
        f"{PROBE_YEARS_BACK + 1} years.\n  " + "\n  ".join(errors)
    )


def _collect_year(ctx, year: int, tables: list[str], prefixes: tuple[str, ...],
                  ) -> tuple[dict[str, dict[str, str]], str, str, str]:
    """Merge several tables for one year into one row per GEOID.

    Returns the map, the url of the first table, its retrieval timestamp, and a
    note about any large table that did not make it.
    """
    merged: dict[str, dict[str, str]] = {}
    first_url = ""
    retrieved = ""
    skipped = ""
    for table in tables:
        try:
            rows, url, at = _read_table(ctx, year, table, prefixes)
        except FetchError as exc:
            if table in LARGE_TABLES:
                # Survivable on its own. Every column from the other tables is
                # already in hand, so losing this one costs the age share and
                # nothing else.
                skipped = (
                    f"the {table} summary file did not load, so the columns "
                    f"derived from it are MISSING: {exc}"
                )
                ctx.log(f"ACS summary file: {skipped}")
                continue
            raise
        if not first_url:
            first_url, retrieved = url, at
        for geoid, values in rows.items():
            merged.setdefault(geoid, {}).update(values)
    return merged, first_url, retrieved, skipped


def fetch_maps(ctx, units: list[Unit]):
    """Build the same AcsMaps the API route builds, without a key."""
    from .census_acs import AcsMaps

    prefixes = _state_prefixes(ctx, units)
    latest_year = _probe_year(ctx, prefixes)
    prior_year = latest_year - 5          # non-overlapping five-year samples

    latest_tables = ["b01003", "b11001", "b25003", "b19013", "b01002", "b25064", "b01001"]
    latest, latest_url, retrieved_latest, skipped = _collect_year(
        ctx, latest_year, latest_tables, prefixes
    )

    # The prior vintage only backs the two growth rates, so it needs two tables
    # and its absence is not fatal.
    prior: dict[str, dict[str, str]] = {}
    prior_url = DATA_URL.format(base=BASE, year=prior_year, table="b01003")
    retrieved_prior = ""
    prior_error = ""
    try:
        prior, prior_url, retrieved_prior, _ = _collect_year(
            ctx, prior_year, ["b01003", "b11001"], prefixes
        )
        ctx.log(f"ACS summary file: prior vintage {prior_year} loaded "
                f"({len(prior):,} geographies)")
    except FetchError as exc:
        prior_error = str(exc)
        ctx.log(f"WARNING: the prior ACS summary file vintage {prior_year} did not "
                f"load, so the growth columns will be MISSING: {exc}")

    if skipped:
        prior_error = (prior_error + " | " if prior_error else "") + skipped

    return AcsMaps(
        latest=latest, prior=prior,
        latest_year=latest_year, prior_year=prior_year,
        latest_url=latest_url, prior_url=prior_url,
        retrieved_latest=retrieved_latest, retrieved_prior=retrieved_prior,
        prior_error=prior_error, source_name=SOURCE_NAME,
    )
