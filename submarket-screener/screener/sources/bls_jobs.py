"""County employment and unemployment from the Bureau of Labor Statistics.

Two BLS products are combined here:

  QCEW (Quarterly Census of Employment and Wages) open data CSVs give total
  covered employment for a county, an actual administrative count drawn from
  unemployment insurance filings rather than a survey estimate. We use the
  annual average file and turn it into a 3 year compound annual growth rate.

  LAUS (Local Area Unemployment Statistics) via the BLS public API v2 gives the
  county unemployment rate and labour force. LAUS is a model based estimate,
  not a count.

# LIMITATIONS
# - Everything here is COUNTY level. There is no legal sub-county employment
#   series, so the same county figure is attached to every submarket inside
#   that county. Two submarkets in one county will always score identically on
#   these metrics. They separate counties, not neighbourhoods. If a market
#   config lists only one county, these columns have no discriminating power at
#   all and the scoring weight should reflect that.
# - QCEW counts jobs by the establishment's location, not by where the worker
#   lives. LAUS counts people by where they live. The two are not comparable
#   and must not be netted against each other.
# - QCEW covers only employment subject to unemployment insurance. The
#   self employed, most farm proprietors, some agricultural labour, railroad
#   workers and some non profit and religious staff are outside the universe.
# - QCEW cells are suppressed for confidentiality when too few establishments
#   exist. A suppressed figure arrives with a disclosure_code and is returned
#   as MISSING here, never as a zero.
# - The annual average file for a year is published with a long lag (often the
#   following autumn), so the latest available year is usually two years behind
#   the current calendar year.
# - LAUS county estimates are modelled from state level inputs and are revised
#   every year. The number you pull today for 2023 may not be the number you
#   pull next spring.
# - A 3 year CAGR hides the path. A county that crashed and recovered and a
#   county that grew steadily can produce the same number.
# - County boundaries and FIPS codes change occasionally (Connecticut replaced
#   its counties with planning regions in 2022). A FIPS code that stops
#   returning data returns MISSING here rather than being silently remapped.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import date

from .. import cache as cache_module
from .. import provenance
from ..cache import FetchError
from ..context import Context
from ..provenance import MetricSpec, Unit, Value

SOURCE_NAME = "BLS QCEW open data and BLS LAUS public API v2"

# --------------------------------------------------------------------- config

# QCEW open data CSV, no API key. 'a' in the path means annual averages.
# Confirmed pattern from the BLS QCEW open data documentation. The user should
# eyeball one downloaded file on the first online run to confirm the header row
# has not moved, because this module will raise loudly if it has.
QCEW_AREA_CSV_URL = "https://data.bls.gov/cew/data/api/{year}/a/area/{fips5}.csv"

# BLS public API v2. POST with a JSON body. Requires a free registration key.
BLS_API_V2_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

ENV_BLS_KEY = "BLS_API_KEY"
HOW_TO_GET_KEY = (
    "Register free at https://data.bls.gov/registrationEngine/ and you get the "
    "key by email within a minute."
)

# In the QCEW annual file, the county total across every ownership and every
# industry is the single row where own_code is '0' (Total Covered) and
# industry_code is '10' (Total, all industries).
QCEW_TOTAL_OWN_CODE = "0"
QCEW_TOTAL_INDUSTRY_CODE = "10"

# Columns we actually read plus the ones whose presence proves we have the file
# we think we have. If any of these are absent the layout changed and we raise.
QCEW_REQUIRED_COLUMNS = (
    "area_fips",
    "own_code",
    "industry_code",
    "agglvl_code",
    "year",
    "qtr",
    "annual_avg_emplvl",
    "disclosure_code",
)

# How far back to probe for the newest published annual file, starting at
# current calendar year minus 1.
QCEW_PROBE_YEARS = 4
# The growth window. 3 years back from the latest year with data.
CAGR_YEARS = 3

# LAUS measure codes.
LAUS_MEASURE_UNEMPLOYMENT_RATE = "03"
LAUS_MEASURE_UNEMPLOYMENT_LEVEL = "04"
LAUS_MEASURE_EMPLOYMENT = "05"
LAUS_MEASURE_LABOR_FORCE = "06"

# BLS accepts at most 50 series in one v2 request for a registered key.
LAUS_MAX_SERIES_PER_REQUEST = 50
# Annual averages arrive in the monthly series under the pseudo period M13.
LAUS_ANNUAL_PERIOD = "M13"
# How many calendar years of LAUS to ask for. We only want the newest annual
# average, but asking for a window means a publication lag does not come back
# empty handed.
LAUS_YEARS_BACK = 4

# LAUS series IDs are built as:
#   'LA' + seasonal adjustment code (1) + area code (15) + measure code (2)
# For a county the 15 character area code is 'CN' + 5 digit FIPS + 8 zeros.
# That makes a 20 character series ID, for example LAUCN361190000000003.
#
# NOTE FOR THE READER: the brief for this module described the county series as
# 18 characters, built as 'LAU' + 'CN' + FIPS5 + 7 zeros + measure. That recipe
# is internally inconsistent (3 + 2 + 5 + 7 + 2 is 19, not 18) and it does not
# match the published LAUS layout, which pads the area code to 15 characters
# with 8 zeros. Sending a 19 character ID to the API returns an empty series
# rather than an error, which is exactly the silent failure this project is
# built to avoid, so the documented 20 character layout is used here. Confirm
# one ID against https://data.bls.gov/timeseries/LAUCN361190000000003 on the
# first online run.
LAUS_AREA_PAD = "0" * 8
LAUS_SERIES_ID_LENGTH = 20

_QCEW_SOURCE = "BLS Quarterly Census of Employment and Wages (open data CSV)"
_LAUS_SOURCE = "BLS Local Area Unemployment Statistics (public API v2)"

METRICS: list[MetricSpec] = [
    MetricSpec(
        key="county_emp_cagr_3y",
        label="County employment CAGR, 3yr",
        pillar="demand",
        higher_is_better=True,
        unit="%",
        decimals=1,
        scored=True,
        description=(
            "Compound annual growth rate of total covered employment in the "
            "county over three years, from QCEW annual averages. County level, "
            "so every submarket in the county gets the same figure."
        ),
    ),
    MetricSpec(
        key="county_unemployment_rate",
        label="County unemployment rate",
        pillar="demand",
        higher_is_better=False,
        unit="%",
        decimals=1,
        scored=True,
        description=(
            "Latest annual average unemployment rate for the county, from BLS "
            "LAUS. County level, so every submarket in the county gets the "
            "same figure."
        ),
    ),
]

CONTEXT_COLUMNS: list[MetricSpec] = [
    MetricSpec(
        key="county_employment_latest",
        label="County covered employment (latest)",
        pillar="demand",
        higher_is_better=True,
        unit="jobs",
        decimals=0,
        scored=False,
        description=(
            "Total covered employment in the county, QCEW annual average for "
            "the latest published year. Context only, not scored."
        ),
    ),
    MetricSpec(
        key="county_employment_year",
        label="County employment year",
        pillar="demand",
        higher_is_better=True,
        unit="",
        decimals=0,
        scored=False,
        description="The QCEW annual average year the employment figures use.",
    ),
    MetricSpec(
        key="county_labor_force",
        label="County labour force (latest)",
        pillar="demand",
        higher_is_better=True,
        unit="people",
        decimals=0,
        scored=False,
        description=(
            "Latest annual average civilian labour force for the county, from "
            "BLS LAUS. Context only, not scored."
        ),
    ),
    MetricSpec(
        key="county_unemployment_year",
        label="County unemployment year",
        pillar="demand",
        higher_is_better=True,
        unit="",
        decimals=0,
        scored=False,
        description="The LAUS annual average year the unemployment figures use.",
    ),
]

_ALL_KEYS = [spec.key for spec in METRICS] + [spec.key for spec in CONTEXT_COLUMNS]


# ----------------------------------------------------------------- small bits


def build_laus_series_id(fips5: str, measure_code: str) -> str:
    """Build a county LAUS series ID and prove its shape before we send it.

    Raises ValueError rather than returning a malformed ID, because BLS answers
    a malformed but well formed looking ID with an empty series and HTTP 200.
    """
    fips5 = str(fips5).strip()
    measure_code = str(measure_code).strip()
    if len(fips5) != 5 or not fips5.isdigit():
        raise ValueError(
            f"county FIPS must be 5 digits for a LAUS series ID, got {fips5!r}"
        )
    if len(measure_code) != 2 or not measure_code.isdigit():
        raise ValueError(
            f"LAUS measure code must be 2 digits, got {measure_code!r}"
        )
    # 'LA' + 'U' (not seasonally adjusted) + 15 char area code + measure.
    series_id = "LAU" + "CN" + fips5 + LAUS_AREA_PAD + measure_code
    if len(series_id) != LAUS_SERIES_ID_LENGTH:
        raise ValueError(
            f"built LAUS series ID {series_id!r} is {len(series_id)} characters, "
            f"expected {LAUS_SERIES_ID_LENGTH}"
        )
    return series_id


def county_caveat(county_label: str) -> str:
    """The sentence every single Value from this module has to carry."""
    return (
        f"COUNTY LEVEL FIGURE. This is measured for {county_label} as a whole "
        f"and applied unchanged to every submarket in that county, so two "
        f"submarkets in the same county will always score identically on it. "
        f"It separates counties, not neighbourhoods."
    )


def _county_label(fips5: str, name: str) -> str:
    name = (name or "").strip()
    return f"{name} ({fips5})" if name else f"county {fips5}"


def _missing_with_notes(reason: str, *, source: str, vintage: str, url: str,
                        notes: str, retrieved_at: str = "") -> Value:
    """provenance.missing() plus the notes and retrieved_at fields it omits."""
    val = provenance.missing(reason, source=source, vintage=vintage, url=url)
    val.notes = notes
    val.retrieved_at = retrieved_at
    return val


def _county_fips_for(unit: Unit) -> str:
    """Best available county FIPS for a unit, without guessing.

    A 10 character county subdivision GEOID is state(2) + county(3) +
    cousub(5), so the county is recoverable from the GEOID itself. A 7
    character place GEOID carries no county, because places can straddle county
    lines, so there is nothing to fall back on there.
    """
    fips = (unit.county_fips or "").strip()
    if len(fips) == 5 and fips.isdigit():
        return fips
    geoid = (unit.geoid or "").strip()
    if len(geoid) == 10 and geoid.isdigit():
        return geoid[:5]
    return ""


# ------------------------------------------------------------------ QCEW part


@dataclass
class _QcewRow:
    """One parsed county total row."""

    year: int
    employment: int | None = None
    suppressed: bool = False
    problem: str = ""          # empty when employment is usable
    url: str = ""
    retrieved_at: str = ""


def parse_qcew_annual_csv(text: str, fips5: str, year: int, url: str) -> _QcewRow:
    """Pull the county total covered employment row out of a QCEW area CSV.

    Raises FetchError if the file does not look like a QCEW area file at all.
    Returns a _QcewRow with problem set (and employment None) when the file is
    fine but the figure is not usable, which is a data condition, not a bug.
    """
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [f.strip() for f in (reader.fieldnames or [])]
    missing_cols = [c for c in QCEW_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_cols:
        raise FetchError(
            f"QCEW area file {url} does not have the expected columns. "
            f"Missing {missing_cols}. Expected at least {list(QCEW_REQUIRED_COLUMNS)}, "
            f"got {fieldnames}. The QCEW open data layout may have changed; "
            f"refusing to guess which column holds employment."
        )

    matches: list[dict[str, str]] = []
    for raw in reader:
        row = {k: (v or "").strip() for k, v in raw.items() if k is not None}
        if row.get("area_fips", "").zfill(5) != fips5:
            continue
        # own_code '0' is Total Covered (all ownerships), industry_code '10' is
        # Total, all industries. Together they are the county wide total. We do
        # not filter on agglvl_code because BLS has renumbered aggregation
        # levels in the past and own/industry are the stable identifiers.
        if row.get("own_code") != QCEW_TOTAL_OWN_CODE:
            continue
        if row.get("industry_code") != QCEW_TOTAL_INDUSTRY_CODE:
            continue
        matches.append(row)

    if not matches:
        return _QcewRow(
            year=year,
            problem=(
                f"QCEW {year} annual file for {fips5} has no total covered row "
                f"(own_code={QCEW_TOTAL_OWN_CODE}, "
                f"industry_code={QCEW_TOTAL_INDUSTRY_CODE})"
            ),
            url=url,
        )
    if len(matches) > 1:
        raise FetchError(
            f"QCEW area file {url} has {len(matches)} rows matching "
            f"own_code={QCEW_TOTAL_OWN_CODE} and "
            f"industry_code={QCEW_TOTAL_INDUSTRY_CODE} for area {fips5}. "
            f"Exactly one was expected in an annual average file. Refusing to "
            f"pick one arbitrarily."
        )

    row = matches[0]

    file_year = row.get("year", "")
    if file_year and file_year != str(year):
        raise FetchError(
            f"QCEW area file {url} reports year {file_year!r} in the row but "
            f"{year} was requested. The URL to year mapping may have changed."
        )

    # A non empty disclosure_code (normally 'N') means BLS suppressed the cell
    # to protect an identifiable employer. The employment column in that case
    # is published as 0, which is why this check must come BEFORE the numeric
    # parse. Reading it as zero would make a suppressed county look like it has
    # no jobs at all.
    disclosure = row.get("disclosure_code", "")
    if disclosure:
        return _QcewRow(
            year=year,
            suppressed=True,
            problem=(
                f"suppressed by BLS disclosure rules "
                f"(disclosure_code={disclosure!r}) in QCEW {year} for {fips5}"
            ),
            url=url,
        )

    raw_emp = row.get("annual_avg_emplvl", "").replace(",", "")
    if raw_emp == "":
        return _QcewRow(
            year=year,
            problem=f"QCEW {year} total row for {fips5} has a blank annual_avg_emplvl",
            url=url,
        )
    try:
        employment = int(float(raw_emp))
    except ValueError:
        raise FetchError(
            f"QCEW area file {url} has a non numeric annual_avg_emplvl "
            f"{raw_emp!r} on the county total row for {fips5}."
        ) from None

    return _QcewRow(year=year, employment=employment, url=url)


def _fetch_qcew_year(ctx: Context, fips5: str, year: int) -> tuple[str, str, str]:
    """Fetch one QCEW annual area file.

    Returns (text, url, retrieved_at). Raises FetchError, which the caller
    treats as 'that year is not published yet' while probing.
    """
    url = QCEW_AREA_CSV_URL.format(year=year, fips5=fips5)
    resp = ctx.cache.get(
        url,
        key=f"qcew_annual_area_{fips5}_{year}",
        # Annual averages for a closed year never change except at the annual
        # revision, so a long TTL is safe and keeps the demo offline friendly.
        ttl_days=90,
    )
    return resp.text, url, resp.retrieved_at


@dataclass
class _CountyQcew:
    fips5: str
    latest: _QcewRow | None = None
    base: _QcewRow | None = None
    latest_reason: str = ""
    base_reason: str = ""
    attempts: list[str] = field(default_factory=list)
    probe_url: str = ""


def _collect_county_qcew(ctx: Context, fips5: str) -> _CountyQcew:
    """Probe backwards for the newest usable QCEW year, then the base year."""
    out = _CountyQcew(fips5=fips5)
    first_year = date.today().year - 1
    out.probe_url = QCEW_AREA_CSV_URL.format(year=first_year, fips5=fips5)

    for offset in range(QCEW_PROBE_YEARS):
        year = first_year - offset
        try:
            text, url, retrieved_at = _fetch_qcew_year(ctx, fips5, year)
        except FetchError as exc:
            # A year that is not published yet is a 404, which arrives here as
            # a FetchError. That is expected while probing, so keep going.
            out.attempts.append(f"{year}: {exc}")
            continue
        # Parsing happens outside the try on purpose: a layout change must
        # escape as a loud FetchError, not be swallowed as 'try an older year'.
        row = parse_qcew_annual_csv(text, fips5, year, url)
        row.retrieved_at = retrieved_at
        if row.employment is None:
            out.attempts.append(f"{year}: {row.problem}")
            continue
        out.latest = row
        break

    if out.latest is None:
        suppressed_years = [a for a in out.attempts if "suppressed by BLS" in a]
        if suppressed_years:
            out.latest_reason = (
                "suppressed by BLS disclosure rules; no unsuppressed QCEW "
                f"annual total for county {fips5} in the last "
                f"{QCEW_PROBE_YEARS} published years ({'; '.join(out.attempts)})"
            )
        else:
            out.latest_reason = (
                f"no QCEW annual total covered employment found for county "
                f"{fips5} in years {first_year - QCEW_PROBE_YEARS + 1} to "
                f"{first_year} ({'; '.join(out.attempts) or 'no detail'})"
            )
        out.base_reason = out.latest_reason
        return out

    base_year = out.latest.year - CAGR_YEARS
    try:
        text, url, retrieved_at = _fetch_qcew_year(ctx, fips5, base_year)
    except FetchError as exc:
        out.base_reason = (
            f"QCEW base year {base_year} file for county {fips5} could not be "
            f"fetched, so a {CAGR_YEARS} year CAGR cannot be computed: {exc}"
        )
        return out

    base_row = parse_qcew_annual_csv(text, fips5, base_year, url)
    base_row.retrieved_at = retrieved_at
    if base_row.employment is None:
        out.base_reason = (
            f"{CAGR_YEARS} year CAGR needs QCEW {base_year} as the base year "
            f"and it is not usable: {base_row.problem}"
        )
        return out
    out.base = base_row
    return out


def compute_cagr(base_value: float, latest_value: float, years: int) -> float | None:
    """Compound annual growth rate in percent, or None where it is undefined.

    A base of zero or less has no defined growth rate. Returning None here is
    what stops a divide by zero from becoming a fabricated number downstream.
    """
    if years <= 0 or base_value <= 0 or latest_value < 0:
        return None
    return ((latest_value / base_value) ** (1.0 / years) - 1.0) * 100.0


# ------------------------------------------------------------------ LAUS part


@dataclass
class _LausObs:
    year: int
    value: float


def _laus_cache_key(series_ids: list[str], start_year: int, end_year: int) -> str:
    """Deterministic cache key for a POST body.

    ctx.cache keys off the string we hand it, and a POST body is not part of
    the URL, so every request to the same endpoint would otherwise collide. We
    hash the sorted series IDs plus the year range. The registration key is
    deliberately not part of this, so rotating the key does not throw the cache
    away and no secret ends up in a filename.
    """
    payload = ",".join(sorted(series_ids)) + f"|{start_year}-{end_year}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"bls_laus_v2_{start_year}_{end_year}_{len(series_ids)}series_{digest}"


def parse_laus_response(text: str, url: str) -> dict[str, _LausObs]:
    """Parse a BLS v2 timeseries response into {series_id: newest annual obs}.

    BLS answers a bad request with HTTP 200 and a status field in the body, so
    the cache layer never sees a failure. Checking status here is the only
    thing standing between a typo and a workbook full of silent blanks.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(
            f"BLS v2 response from {url} is not valid JSON: {exc}"
        ) from exc

    status = payload.get("status", "")
    if status != "REQUEST_SUCCEEDED":
        messages = payload.get("message", [])
        raise FetchError(
            f"BLS v2 request to {url} returned status {status!r} with HTTP 200. "
            f"Messages: {messages}"
        )

    results = payload.get("Results")
    if not isinstance(results, dict) or "series" not in results:
        raise FetchError(
            f"BLS v2 response from {url} succeeded but has no Results.series "
            f"block. Top level keys were {sorted(payload.keys())}. The API "
            f"layout may have changed."
        )

    out: dict[str, _LausObs] = {}
    for series in results.get("series") or []:
        series_id = str(series.get("seriesID", "")).strip()
        if not series_id:
            raise FetchError(
                f"BLS v2 response from {url} contains a series with no "
                f"seriesID, so observations cannot be attributed to a county."
            )
        best: _LausObs | None = None
        for obs in series.get("data") or []:
            # M13 is the annual average pseudo period in a monthly series.
            if str(obs.get("period", "")).strip() != LAUS_ANNUAL_PERIOD:
                continue
            raw_year = str(obs.get("year", "")).strip()
            raw_value = str(obs.get("value", "")).strip().replace(",", "")
            if not raw_year.isdigit() or raw_value in ("", "-", "(NA)"):
                continue
            try:
                value = float(raw_value)
            except ValueError:
                continue
            year = int(raw_year)
            if best is None or year > best.year:
                best = _LausObs(year=year, value=value)
        if best is not None:
            out[series_id] = best
    return out


def _fetch_laus(ctx: Context, series_ids: list[str], api_key: str,
                start_year: int, end_year: int) -> tuple[dict[str, _LausObs], str]:
    """One batched POST to the BLS v2 API. Returns (observations, retrieved_at)."""
    body = {
        "seriesid": sorted(series_ids),
        "startyear": str(start_year),
        "endyear": str(end_year),
        "annualaverage": True,
        "registrationkey": api_key,
    }
    resp = ctx.cache.get(
        BLS_API_V2_URL,
        key=_laus_cache_key(series_ids, start_year, end_year),
        method="POST",
        json_body=body,
        # LAUS county estimates are revised annually, so do not hold them as
        # long as a closed QCEW year.
        ttl_days=30,
    )
    return parse_laus_response(resp.text, BLS_API_V2_URL), resp.retrieved_at


@dataclass
class _CountyLaus:
    rate: _LausObs | None = None
    labor_force: _LausObs | None = None
    reason: str = ""
    retrieved_at: str = ""


def _collect_county_laus(ctx: Context, county_fips: list[str],
                         api_key: str) -> dict[str, _CountyLaus]:
    """Fetch unemployment rate and labour force for every county, batched."""
    out: dict[str, _CountyLaus] = {f: _CountyLaus() for f in county_fips}
    if not county_fips:
        return out

    end_year = date.today().year
    start_year = end_year - LAUS_YEARS_BACK

    wanted: list[tuple[str, str, str]] = []   # (series_id, fips, measure)
    for fips5 in county_fips:
        try:
            rate_id = build_laus_series_id(fips5, LAUS_MEASURE_UNEMPLOYMENT_RATE)
            lf_id = build_laus_series_id(fips5, LAUS_MEASURE_LABOR_FORCE)
        except ValueError as exc:
            out[fips5].reason = f"cannot build a LAUS series ID: {exc}"
            continue
        wanted.append((rate_id, fips5, LAUS_MEASURE_UNEMPLOYMENT_RATE))
        wanted.append((lf_id, fips5, LAUS_MEASURE_LABOR_FORCE))

    # Two series per county, so 50 series is 25 counties per request.
    for start in range(0, len(wanted), LAUS_MAX_SERIES_PER_REQUEST):
        chunk = wanted[start:start + LAUS_MAX_SERIES_PER_REQUEST]
        ids = [c[0] for c in chunk]
        try:
            observations, retrieved_at = _fetch_laus(
                ctx, ids, api_key, start_year, end_year
            )
        except FetchError as exc:
            # A batch that fails takes only its own counties down with it.
            for _, fips5, _measure in chunk:
                if not out[fips5].reason:
                    out[fips5].reason = f"BLS LAUS request failed: {exc}"
            continue
        for series_id, fips5, measure in chunk:
            obs = observations.get(series_id)
            entry = out[fips5]
            entry.retrieved_at = retrieved_at
            if obs is None:
                note = (
                    f"BLS LAUS returned no {LAUS_ANNUAL_PERIOD} annual average "
                    f"observation for series {series_id} in {start_year} to "
                    f"{end_year}"
                )
                entry.reason = f"{entry.reason}; {note}" if entry.reason else note
                continue
            if measure == LAUS_MEASURE_UNEMPLOYMENT_RATE:
                entry.rate = obs
            elif measure == LAUS_MEASURE_LABOR_FORCE:
                entry.labor_force = obs
    return out


# -------------------------------------------------------------------- collect


def _values_for_county(fips5: str, county_name: str, qcew: _CountyQcew,
                       laus: _CountyLaus) -> dict[str, Value]:
    """Turn one county's fetched state into the six columns."""
    label = _county_label(fips5, county_name)
    caveat = county_caveat(label)
    out: dict[str, Value] = {}

    # ------------------------------------------------ QCEW derived columns
    latest = qcew.latest
    base = qcew.base

    if latest is None:
        for key in ("county_emp_cagr_3y", "county_employment_latest",
                    "county_employment_year"):
            out[key] = _missing_with_notes(
                qcew.latest_reason or "no QCEW annual total available",
                source=_QCEW_SOURCE,
                vintage="QCEW annual averages",
                url=qcew.probe_url,
                notes=caveat,
            )
    else:
        vintage_latest = f"QCEW annual averages {latest.year}"
        out["county_employment_latest"] = Value(
            latest.employment,
            source=_QCEW_SOURCE,
            vintage=vintage_latest,
            url=latest.url,
            retrieved_at=latest.retrieved_at,
            notes=(
                f"{caveat} Total covered employment (own_code=0, "
                f"industry_code=10), annual average for {latest.year}. Covers "
                f"only jobs subject to unemployment insurance, and counts jobs "
                f"where the establishment sits, not where the worker lives."
            ),
        )
        out["county_employment_year"] = Value(
            latest.year,
            source=_QCEW_SOURCE,
            vintage=vintage_latest,
            url=latest.url,
            retrieved_at=latest.retrieved_at,
            notes=(
                f"{caveat} This is the newest QCEW annual average year that "
                f"returned an unsuppressed county total, found by probing back "
                f"from {date.today().year - 1}."
            ),
        )

        if base is None:
            out["county_emp_cagr_3y"] = _missing_with_notes(
                qcew.base_reason or (
                    f"QCEW base year {latest.year - CAGR_YEARS} not usable"
                ),
                source=_QCEW_SOURCE,
                vintage=f"QCEW annual averages {latest.year}",
                url=latest.url,
                notes=caveat,
                retrieved_at=latest.retrieved_at,
            )
        else:
            cagr = compute_cagr(base.employment, latest.employment, CAGR_YEARS)
            vintage_span = (
                f"QCEW annual averages {base.year} to {latest.year}"
            )
            if cagr is None:
                out["county_emp_cagr_3y"] = _missing_with_notes(
                    (
                        f"QCEW {base.year} base employment for county {fips5} is "
                        f"{base.employment}, so a growth rate is undefined"
                    ),
                    source=_QCEW_SOURCE,
                    vintage=vintage_span,
                    url=latest.url,
                    notes=caveat,
                    retrieved_at=latest.retrieved_at,
                )
            else:
                out["county_emp_cagr_3y"] = Value(
                    round(cagr, 4),
                    source=_QCEW_SOURCE,
                    vintage=vintage_span,
                    url=latest.url,
                    retrieved_at=latest.retrieved_at,
                    notes=(
                        f"{caveat} Compound annual growth of total covered "
                        f"employment from {base.year} ({base.employment:,}) to "
                        f"{latest.year} ({latest.employment:,}), "
                        f"{CAGR_YEARS} years. A CAGR hides the path between the "
                        f"two endpoints. Base year file: {base.url}"
                    ),
                )

    # ------------------------------------------------ LAUS derived columns
    laus_reason = laus.reason or "BLS LAUS returned no annual average observation"
    rate_year = laus.rate.year if laus.rate else None

    if laus.rate is None:
        out["county_unemployment_rate"] = _missing_with_notes(
            laus_reason,
            source=_LAUS_SOURCE,
            vintage="LAUS annual averages",
            url=BLS_API_V2_URL,
            notes=caveat,
            retrieved_at=laus.retrieved_at,
        )
        out["county_unemployment_year"] = _missing_with_notes(
            laus_reason,
            source=_LAUS_SOURCE,
            vintage="LAUS annual averages",
            url=BLS_API_V2_URL,
            notes=caveat,
            retrieved_at=laus.retrieved_at,
        )
    else:
        vintage_rate = f"LAUS annual average {laus.rate.year}"
        out["county_unemployment_rate"] = Value(
            laus.rate.value,
            source=_LAUS_SOURCE,
            vintage=vintage_rate,
            url=BLS_API_V2_URL,
            retrieved_at=laus.retrieved_at,
            notes=(
                f"{caveat} Annual average (period M13) for {laus.rate.year}. "
                f"LAUS county figures are modelled from state inputs, not "
                f"counted, and are revised every year."
            ),
        )
        out["county_unemployment_year"] = Value(
            laus.rate.year,
            source=_LAUS_SOURCE,
            vintage=vintage_rate,
            url=BLS_API_V2_URL,
            retrieved_at=laus.retrieved_at,
            notes=(
                f"{caveat} The LAUS annual average year behind the "
                f"unemployment rate column."
            ),
        )

    if laus.labor_force is None:
        out["county_labor_force"] = _missing_with_notes(
            laus_reason,
            source=_LAUS_SOURCE,
            vintage="LAUS annual averages",
            url=BLS_API_V2_URL,
            notes=caveat,
            retrieved_at=laus.retrieved_at,
        )
    else:
        lf_note = ""
        if rate_year is not None and laus.labor_force.year != rate_year:
            # Worth saying out loud: the two LAUS series can land on different
            # newest years if one is revised ahead of the other.
            lf_note = (
                f" Note the labour force year ({laus.labor_force.year}) differs "
                f"from the unemployment rate year ({rate_year})."
            )
        out["county_labor_force"] = Value(
            int(round(laus.labor_force.value)),
            source=_LAUS_SOURCE,
            vintage=f"LAUS annual average {laus.labor_force.year}",
            url=BLS_API_V2_URL,
            retrieved_at=laus.retrieved_at,
            notes=(
                f"{caveat} Civilian labour force, annual average (period M13) "
                f"for {laus.labor_force.year}. LAUS counts people by where they "
                f"live, unlike QCEW which counts jobs by where they sit, so the "
                f"two must not be netted against each other.{lf_note}"
            ),
        )

    return out


def collect(ctx: Context, units: list[Unit]) -> dict[str, dict[str, Value]]:
    """Return {unit.geoid: {metric_key: Value}} for every unit passed in."""
    # Fail fast and loudly if the free key is absent. There is no unauthenticated
    # v2 endpoint that returns the same numbers, and the v1 endpoint has a
    # different series universe, so degrading is not an option.
    api_key = cache_module.require_key(ENV_BLS_KEY, HOW_TO_GET_KEY)

    # Unique counties, in first seen order so the log reads predictably.
    county_names: dict[str, str] = {}
    for unit in units:
        fips5 = _county_fips_for(unit)
        if fips5 and fips5 not in county_names:
            county_names[fips5] = unit.county_name or ""
    county_fips = list(county_names.keys())

    qcew_by_county: dict[str, _CountyQcew] = {}
    for fips5 in county_fips:
        ctx.log(f"QCEW annual employment for county {fips5}")
        qcew_by_county[fips5] = _collect_county_qcew(ctx, fips5)

    if county_fips:
        ctx.log(
            f"LAUS annual averages for {len(county_fips)} county/counties "
            f"({2 * len(county_fips)} series)"
        )
    laus_by_county = _collect_county_laus(ctx, county_fips, api_key)

    # Build each county's columns once, then hand the same figures to every
    # submarket in that county. This is the whole caveat in one line of code.
    per_county: dict[str, dict[str, Value]] = {}
    for fips5 in county_fips:
        per_county[fips5] = _values_for_county(
            fips5,
            county_names[fips5],
            qcew_by_county[fips5],
            laus_by_county.get(fips5, _CountyLaus()),
        )

    out: dict[str, dict[str, Value]] = {}
    for unit in units:
        fips5 = _county_fips_for(unit)
        if fips5 and fips5 in per_county:
            # Copy so a later consumer mutating one unit's Value cannot silently
            # rewrite every other submarket in the county.
            out[unit.geoid] = {
                key: Value(**val.to_dict())
                for key, val in per_county[fips5].items()
            }
            continue
        reason = (
            f"unit {unit.geoid} has no usable 5 digit county FIPS "
            f"(county_fips={unit.county_fips!r}, geo_type={unit.geo_type!r}), "
            f"so no county level BLS series can be selected for it"
        )
        out[unit.geoid] = {
            key: _missing_with_notes(
                reason,
                source=SOURCE_NAME,
                vintage="",
                url="",
                notes=county_caveat("its county"),
            )
            for key in _ALL_KEYS
        }
    return out
