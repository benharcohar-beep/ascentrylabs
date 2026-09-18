"""Rent level and rent growth per submarket.

Primary source is the Zillow Observed Rent Index (ZORI) at ZIP level, which is
free and needs no key. HUD Fair Market Rents are pulled alongside it as an
independent, administratively produced cross-check so a reader can see whether
the Zillow number is plausible for the county.

The two sources disagree by construction and that is the point of carrying
both. ZORI is an asking rent index built from Zillow listings. FMR is a HUD
administrative figure for the voucher programme. If ZORI comes in below FMR for
a suburban submarket, something is wrong with the ZIP aggregation and the
zori_vs_fmr_ratio column is there to make that obvious.

# LIMITATIONS
# - ZORI is an index of ASKING rents on Zillow listings, not achieved rents and
#   not a survey of the whole stock. It skews towards professionally managed,
#   listed units and away from small private landlords, and Zillow smooths it.
# - Zillow suppresses ZIPs with thin listing samples. Rural and small suburban
#   ZCTAs are frequently absent entirely, so a submarket can be legitimately
#   uncoverable. This module reports that as MISSING, never as a number taken
#   from one unrepresentative ZIP.
# - ZCTA boundaries are not municipal boundaries. The ZIP to submarket weights
#   come from land area of overlap, so they say nothing about where the rental
#   units actually sit inside the ZIP. A submarket whose rentals are all in one
#   corner of a large ZCTA will be mis-weighted and this module cannot detect
#   that.
# - ZORI mixes single family, condo and multifamily. It is not a stabilised
#   class A apartment rent and must not be quoted as one.
# - ZORI is not bedroom controlled. A submarket of large new single family
#   rentals will show a higher ZORI than a submarket of one bedroom flats with
#   no difference in rent per square foot.
# - HUD FMR is set at roughly the 40th percentile of standard quality rents and
#   is published once a fiscal year, so it lags and sits below market. It is a
#   floor-ish sanity check, never a market rent, and it is a county figure so it
#   cannot separate submarkets inside a county.
# - Counties in Small Area FMR metros get ZIP level FMRs instead of one county
#   figure. Where HUD returns no county-wide figure this module reports MISSING
#   rather than averaging the small areas, because an unweighted average of ZIP
#   FMRs is not a HUD published number.
# - Zillow renames its research CSVs from time to time. A 404 here means the
#   file name constant below is stale, not that the data is gone.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone
from typing import Any, Iterable

from ..cache import CachedResponse, FetchError, require_key
from ..context import Context
from ..provenance import MetricSpec, Unit, Value, missing

SOURCE_NAME = "Zillow ZORI (ZIP level) with HUD Fair Market Rents cross-check"

# --------------------------------------------------------------------------
# Source 1: Zillow research CSVs.
# --------------------------------------------------------------------------
ZORI_BASE_URL = "https://files.zillowstatic.com/research/public_csvs/zori/"

# IMPORTANT: Zillow renames these research files from time to time (the
# "uc_sfrcondomfr_sm_month" suffix has changed before). If the download 404s,
# check the current file name on https://www.zillow.com/research/data/ and
# update the constant. Do not guess at a name.
ZORI_ZIP_FILE = "Zip_zori_uc_sfrcondomfr_sm_month.csv"

# The metro level file, kept here so the documented name lives in one place.
# It is deliberately NOT used as a silent fallback for unit level numbers: a
# metro figure applied to every submarket would hand every row of the screen
# the same rent and the same growth, which tells the ranking nothing and would
# be an invented attribution of a metro figure to a township. If the ZIP file
# disappears, a human decides what to do.
ZORI_METRO_FILE = "Metro_zori_uc_sfrcondomfr_sm_month.csv"

ZORI_URL = ZORI_BASE_URL + ZORI_ZIP_FILE

# Below this share of the submarket's ZCTA weight we refuse to report a number.
# A single covered ZIP out of five is not "the rent in this township", it is
# the rent in one ZIP, and reporting it would quietly put a wrong number into a
# scored column.
MIN_ZIP_COVERAGE = 0.25

# A ZORI file with fewer month columns than this is not the file we think it
# is. 24 is the minimum needed for a year on year figure plus a year of history
# to eyeball it against.
MIN_MONTH_COLUMNS = 24

# Month column headers are ISO dates like 2015-01-31. A few of these formats
# have shown up across Zillow file vintages, so try each one. Anything that
# parses as a date is a month column, anything that does not is an identifier
# column. This is why the module never hardcodes "the first 9 columns".
_MONTH_HEADER_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m")

ZORI_NOTES = (
    "ZORI is a repeat-rent index of asking rents on Zillow listings. It is "
    "smoothed and is not a survey of the whole rental stock. It skews to "
    "professionally managed and listed units, and Zillow drops small ZIPs for "
    "sample size reasons, so coverage is uneven. Submarket figures are a "
    "land-area weighted average of the overlapping ZCTAs that Zillow publishes."
)

# --------------------------------------------------------------------------
# Source 2: HUD Fair Market Rents API.
# --------------------------------------------------------------------------
HUD_FMR_BASE_URL = "https://www.huduser.gov/hudapi/public/fmr/data/"

# HUD entity ids for a county are the 5 digit county FIPS followed by 99999.
_HUD_COUNTY_SUFFIX = "99999"

# How many fiscal years to probe backwards, starting at the current calendar
# year plus one. HUD publishes FY n+1 partway through calendar year n, so the
# newest year may or may not exist yet on any given day.
FMR_YEAR_ATTEMPTS = 3

FMR_NOTES = (
    "HUD Fair Market Rent is an administrative figure set for the housing "
    "choice voucher programme at roughly the 40th percentile of standard "
    "quality rents in the area. It is a floor-ish cross-check and not a market "
    "rent, it is published once a fiscal year so it lags, and it is a county "
    "figure so it cannot distinguish submarkets within a county."
)

HUD_KEY_HELP = (
    "Create a free account at "
    "https://www.huduser.gov/portal/dataset/fmr-api.html , then generate a "
    "token under your HUD User account API page. It is issued instantly."
)

# --------------------------------------------------------------------------
# Column definitions.
# --------------------------------------------------------------------------
METRICS: list[MetricSpec] = [
    MetricSpec(
        key="zori_latest",
        label="ZORI rent, latest month",
        pillar="rent",
        higher_is_better=True,
        unit="$",
        decimals=0,
        description=(
            "Latest Zillow Observed Rent Index value in dollars per month, "
            "land-area weighted across the ZCTAs overlapping this submarket."
        ),
    ),
    MetricSpec(
        key="zori_yoy",
        label="ZORI rent growth, 1 year",
        pillar="rent",
        higher_is_better=True,
        unit="%",
        decimals=1,
        description=(
            "Percent change in the weighted ZORI series against the same month "
            "one year earlier, using only ZCTAs present at both ends."
        ),
    ),
    MetricSpec(
        key="zori_cagr_3y",
        label="ZORI rent growth, 3 year CAGR",
        pillar="rent",
        higher_is_better=True,
        unit="%",
        decimals=1,
        description=(
            "Compound annual growth rate of the weighted ZORI series over the "
            "36 months to the latest month, using only ZCTAs present at both "
            "ends."
        ),
    ),
]

CONTEXT_COLUMNS: list[MetricSpec] = [
    MetricSpec(
        key="zori_month",
        label="ZORI month",
        pillar="rent",
        higher_is_better=True,
        unit="",
        decimals=0,
        scored=False,
        description="Month label of the latest ZORI observation used, e.g. 2026-07.",
    ),
    MetricSpec(
        key="zori_zip_coverage",
        label="ZORI ZIP coverage",
        pillar="rent",
        higher_is_better=True,
        unit="",
        decimals=2,
        scored=False,
        description=(
            "Share of this submarket's ZCTA weight that actually had ZORI data "
            "in the latest month, 0 to 1. Read every rent figure next to this."
        ),
    ),
    MetricSpec(
        key="zori_zips_used",
        label="ZORI ZCTAs used",
        pillar="rent",
        higher_is_better=True,
        unit="",
        decimals=0,
        scored=False,
        description="Comma separated ZCTAs that contributed to the latest month.",
    ),
    MetricSpec(
        key="fmr_2br",
        label="HUD FMR, 2 bedroom",
        pillar="rent",
        higher_is_better=True,
        unit="$",
        decimals=0,
        scored=False,
        description="HUD Fair Market Rent for a 2 bedroom unit, county level.",
    ),
    MetricSpec(
        key="fmr_year",
        label="HUD FMR fiscal year",
        pillar="rent",
        higher_is_better=True,
        unit="",
        decimals=0,
        scored=False,
        description="Fiscal year of the HUD FMR figure.",
    ),
    MetricSpec(
        key="zori_vs_fmr_ratio",
        label="ZORI to FMR ratio",
        pillar="rent",
        higher_is_better=True,
        unit="",
        decimals=2,
        scored=False,
        description=(
            "zori_latest divided by fmr_2br. A sanity cross-check, not a "
            "metric. Values near or below 1.0 deserve investigation because "
            "FMR is meant to sit near the 40th percentile."
        ),
    ),
]

_ALL_KEYS = [m.key for m in METRICS] + [m.key for m in CONTEXT_COLUMNS]


# --------------------------------------------------------------------------
# Small helpers.
# --------------------------------------------------------------------------
def _missing_with_notes(reason: str, *, source: str = "", vintage: str = "",
                        url: str = "", notes: str = "") -> Value:
    """provenance.missing(), but carrying the caveats a reader needs anyway.

    A MISSING cell still has to explain what the source would have been and why
    it cannot be trusted blindly, otherwise the reader fills the gap from
    memory.
    """
    value = missing(reason, source=source, vintage=vintage, url=url)
    value.notes = notes
    return value


def _zori_missing(reason: str, *, vintage: str = "", retrieved_at: str = "") -> Value:
    value = _missing_with_notes(
        reason, source=SOURCE_NAME, vintage=vintage, url=ZORI_URL, notes=ZORI_NOTES
    )
    value.retrieved_at = retrieved_at
    return value


def _fmr_missing(reason: str, *, url: str = "", vintage: str = "",
                 retrieved_at: str = "") -> Value:
    value = _missing_with_notes(
        reason, source="HUD User Fair Market Rents API", vintage=vintage,
        url=url or HUD_FMR_BASE_URL, notes=FMR_NOTES,
    )
    value.retrieved_at = retrieved_at
    return value


def _month_label(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _parse_month_header(name: str) -> date | None:
    """Return the date a column header encodes, or None if it is not a month."""
    text = (name or "").strip()
    if not text:
        return None
    for fmt in _MONTH_HEADER_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _normalise_zcta(raw: str) -> str:
    """Zero-pad a ZIP to 5 characters.

    Zillow's RegionName is the 5 digit ZIP as text. Anything that reads the file
    with an integer dtype silently turns 01234 into 1234 and then fails to match
    a single New England ZCTA, so the whole file is read as strings and padded
    here.
    """
    text = (raw or "").strip()
    if text.isdigit():
        return text.zfill(5)
    return text


def _collapse_weights(zctas: Iterable[tuple[str, float]]) -> list[tuple[str, float]]:
    """Sum duplicate ZCTAs and drop non-positive weights."""
    acc: dict[str, float] = {}
    for zcta, weight in zctas:
        key = _normalise_zcta(str(zcta))
        try:
            w = float(weight)
        except (TypeError, ValueError):
            continue
        if w <= 0:
            continue
        acc[key] = acc.get(key, 0.0) + w
    return sorted(acc.items())


# --------------------------------------------------------------------------
# ZORI parsing.
# --------------------------------------------------------------------------
def parse_zori_csv(
    text: str, *, wanted: set[str] | None = None, file_name: str = ZORI_ZIP_FILE
) -> tuple[list[date], dict[str, dict[date, float]]]:
    """Parse a Zillow ZIP level ZORI CSV.

    Returns (months ascending, {zcta5: {month_date: value}}). Only ZCTAs in
    `wanted` are kept when `wanted` is given, which keeps the whole national
    file from sitting in memory for a five county screen.

    Raises FetchError on anything that suggests the layout moved.
    """
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise FetchError(
            f"{file_name} from {ZORI_BASE_URL} was empty. Zillow renames these "
            f"files from time to time, so check the current file name on "
            f"https://www.zillow.com/research/data/ if the download 404s."
        ) from exc

    lookup = {name.strip().lower(): i for i, name in enumerate(header)}
    if "regionname" not in lookup:
        raise FetchError(
            f"{file_name} from {ZORI_BASE_URL} has no RegionName column; "
            f"found {header[:10]}. Expected Zillow identifier columns "
            f"(RegionID, SizeRank, RegionName, RegionType, StateName, ...) "
            f"followed by one column per month. Zillow renames these files "
            f"from time to time, so check the current file name on "
            f"https://www.zillow.com/research/data/ if the download 404s."
        )
    region_idx = lookup["regionname"]

    # Every column whose header parses as a date is a month column. This is
    # deliberately not "everything after column N": Zillow has added and
    # removed identifier columns (State, City, Metro, CountyName) between
    # vintages, and a fixed offset would silently shift the whole series.
    month_cols: list[tuple[date, int]] = []
    for idx, name in enumerate(header):
        if idx == region_idx:
            continue
        parsed = _parse_month_header(name)
        if parsed is not None:
            month_cols.append((parsed, idx))
    month_cols.sort(key=lambda pair: pair[0])

    if len(month_cols) < MIN_MONTH_COLUMNS:
        raise FetchError(
            f"{file_name} from {ZORI_BASE_URL} has only {len(month_cols)} "
            f"parseable month columns, expected at least {MIN_MONTH_COLUMNS}. "
            f"Zillow renames these files from time to time, so check the "
            f"current file name on https://www.zillow.com/research/data/ if "
            f"the download 404s."
        )

    months = [d for d, _ in month_cols]
    series: dict[str, dict[date, float]] = {}
    for row in reader:
        if len(row) <= region_idx:
            continue
        zcta = _normalise_zcta(row[region_idx])
        if not zcta:
            continue
        if wanted is not None and zcta not in wanted:
            continue
        points: dict[date, float] = {}
        for month, idx in month_cols:
            if idx >= len(row):
                continue
            cell = row[idx].strip()
            if not cell:
                # A blank is genuinely "Zillow published nothing for this ZIP
                # this month". It is never a zero rent.
                continue
            try:
                points[month] = float(cell)
            except ValueError:
                # A stray non-numeric cell in a month column is a layout
                # problem, not a data problem.
                raise FetchError(
                    f"{file_name} from {ZORI_BASE_URL} has non-numeric value "
                    f"'{cell[:40]}' in month column {_month_label(month)} for "
                    f"RegionName '{zcta}'. Expected a rent index value. "
                    f"Zillow renames these files from time to time, so check "
                    f"the current file name on "
                    f"https://www.zillow.com/research/data/ if the download "
                    f"404s."
                ) from None
        if points:
            series[zcta] = points
    return months, series


def _fetch_zori(ctx: Context) -> CachedResponse:
    try:
        return ctx.cache.get(
            ZORI_URL,
            key="zillow_zori_zip_sfrcondomfr_sm_month",
            ttl_days=30,
            # No expect_content_type: files.zillowstatic.com has served these
            # as text/csv and as octet-stream depending on the edge node, and a
            # false failure there would be worse than parsing and finding out.
        )
    except FetchError as exc:
        raise FetchError(
            f"could not download {ZORI_ZIP_FILE} from {ZORI_BASE_URL} ({exc}). "
            f"Zillow renames these files from time to time, so check the "
            f"current file name on https://www.zillow.com/research/data/ if "
            f"the download 404s."
        ) from exc


def _weighted_month(
    series: dict[str, dict[date, float]],
    weights: list[tuple[str, float]],
    month: date,
) -> tuple[float | None, float, list[str]]:
    """Weight-renormalised average across the ZCTAs with data in `month`."""
    covered = 0.0
    acc = 0.0
    used: list[str] = []
    for zcta, weight in weights:
        point = series.get(zcta, {}).get(month)
        if point is None:
            continue
        covered += weight
        acc += weight * point
        used.append(zcta)
    if covered <= 0:
        return None, 0.0, []
    return acc / covered, covered, used


def _weighted_window(
    series: dict[str, dict[date, float]],
    weights: list[tuple[str, float]],
    start: date,
    end: date,
) -> tuple[float, float, float, list[str]] | None:
    """Weighted index at both ends of a window, on one fixed basket of ZCTAs.

    The basket is the ZCTAs with data at BOTH ends, renormalised for this window
    only. Growth is then taken on the weighted series rather than by averaging
    individual ZIP growth rates, which is not the same number once the weights
    differ. Holding the basket fixed also stops a ZIP appearing or disappearing
    mid-window from showing up as rent growth.
    """
    basket = [
        (zcta, weight)
        for zcta, weight in weights
        if series.get(zcta, {}).get(start) is not None
        and series.get(zcta, {}).get(end) is not None
    ]
    total = sum(weight for _, weight in basket)
    if total <= 0:
        return None
    start_value = sum(weight * series[z][start] for z, weight in basket) / total
    end_value = sum(weight * series[z][end] for z, weight in basket) / total
    return start_value, end_value, total, [z for z, _ in basket]


# --------------------------------------------------------------------------
# HUD FMR.
# --------------------------------------------------------------------------
def _hud_entity_id(county_fips: str) -> str:
    """HUD county entity id: 5 digit county FIPS plus 99999, 10 characters."""
    return f"{county_fips.zfill(5)}{_HUD_COUNTY_SUFFIX}"


def _fmr_display_url(entity_id: str, year: int) -> str:
    return f"{HUD_FMR_BASE_URL}{entity_id}?year={year}"


def _normalise_bedroom_key(key: str) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


_TWO_BEDROOM_KEYS = {"twobedroom", "twobedrooms", "2br", "2bedroom", "twobr"}


def _two_bedroom_from_entry(entry: dict[str, Any]) -> float | None:
    for key, raw in entry.items():
        if _normalise_bedroom_key(key) in _TWO_BEDROOM_KEYS:
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None
    return None


def _entry_is_county_wide(entry: dict[str, Any]) -> bool:
    """Is this Small Area FMR list entry the county-wide row?

    HUD's small area responses are a list of ZIP level entries. Where a
    county-wide figure is also returned it comes through without a usable
    zip_code. Anything with a real ZIP in it is a small area and must not be
    treated as the county.
    """
    for key in ("zip_code", "zipcode", "zip", "smallarea_zipcode"):
        if key in entry:
            raw = entry.get(key)
            text = "" if raw is None else str(raw).strip()
            if text and text not in {"0", "00000", "99999", "countywide", "county"}:
                return False
    return True


def _extract_fmr_2br(payload: Any, url: str) -> tuple[float | None, str, str]:
    """Return (two bedroom FMR or None, reason when None, shape description).

    Raises FetchError when the response is shaped in a way this parser does not
    recognise, because a silently mis-read rent is worse than a stopped run.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise FetchError(
            f"HUD FMR response from {url} has no 'data' object. Expected "
            f"{{'data': {{... 'basicdata': ...}}}}. The API layout may have "
            f"changed; check https://www.huduser.gov/portal/dataset/fmr-api.html"
        )
    data = payload["data"]
    basic = data.get("basicdata")

    if isinstance(basic, dict):
        # The ordinary county response: one object of rent values keyed by
        # bedroom count.
        value = _two_bedroom_from_entry(basic)
        shape = "HUD returned the ordinary county-wide basicdata object."
        if value is None:
            return None, (
                "HUD returned a county-wide basicdata object with no "
                "Two-Bedroom figure"
            ), shape
        return value, "", shape

    if isinstance(basic, list):
        # Small Area FMR metro: basicdata is a list of ZIP level entries.
        shape = (
            f"HUD returned a Small Area FMR list of {len(basic)} ZIP level "
            f"entries rather than a single county object."
        )
        for entry in basic:
            if not isinstance(entry, dict):
                continue
            if _entry_is_county_wide(entry):
                value = _two_bedroom_from_entry(entry)
                if value is not None:
                    return value, "", shape + " Used the county-wide entry."
        # Averaging the small areas would produce a number HUD never published,
        # so we refuse.
        return None, (
            "county is Small Area FMR; no single county figure returned"
        ), shape

    raise FetchError(
        f"HUD FMR response from {url} has basicdata of type "
        f"{type(basic).__name__}, expected a dict of rent values or a list of "
        f"small area entries. The API layout may have changed; check "
        f"https://www.huduser.gov/portal/dataset/fmr-api.html"
    )


def _fetch_fmr_for_county(
    ctx: Context, county_fips: str, token: str
) -> dict[str, Any]:
    """Probe fiscal years backwards and return what we found for one county.

    Returns a dict with keys: value, year, url, retrieved_at, reason, shape.
    `value` is None when nothing usable came back, and `reason` says why.
    """
    entity_id = _hud_entity_id(county_fips)
    first_year = datetime.now(timezone.utc).year + 1
    attempts: list[str] = []

    for offset in range(FMR_YEAR_ATTEMPTS):
        year = first_year - offset
        url = _fmr_display_url(entity_id, year)
        try:
            response = ctx.cache.get(
                HUD_FMR_BASE_URL + entity_id,
                key=f"hud_fmr_{entity_id}_fy{year}",
                params={"year": year},
                # The token goes in the header and never into the cache key or
                # the recorded URL.
                headers={"Authorization": f"Bearer {token}"},
                ttl_days=180,
            )
        except FetchError as exc:
            # FY n+1 usually does not exist yet, so a failure on the first
            # attempt is expected rather than alarming.
            attempts.append(f"FY{year}: {exc}")
            continue

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise FetchError(
                f"HUD FMR response from {url} was not JSON: {exc}. The API "
                f"layout may have changed; check "
                f"https://www.huduser.gov/portal/dataset/fmr-api.html"
            ) from exc

        value, reason, shape = _extract_fmr_2br(payload, url)
        # Prefer the year HUD says it gave us over the year we asked for.
        reported_year = payload.get("data", {}).get("year", year)
        try:
            reported_year = int(reported_year)
        except (TypeError, ValueError):
            reported_year = year
        return {
            "value": value,
            "year": reported_year,
            "url": url,
            "retrieved_at": response.retrieved_at,
            "reason": reason,
            "shape": shape,
        }

    return {
        "value": None,
        "year": None,
        "url": _fmr_display_url(entity_id, first_year),
        "retrieved_at": "",
        "reason": (
            f"HUD FMR API returned nothing usable for entity {entity_id} across "
            f"{FMR_YEAR_ATTEMPTS} fiscal years ({'; '.join(attempts)})"
        ),
        "shape": "",
    }


# --------------------------------------------------------------------------
# collect
# --------------------------------------------------------------------------
def collect(ctx: Context, units: list[Unit]) -> dict[str, dict[str, Value]]:
    """Return {unit.geoid: {metric_key: Value}} for every unit passed in.

    Raises MissingCredential when HUD_API_KEY is not set. The HUD key is free
    and issued instantly, and the contract for this project is that a missing
    key stops the run with instructions rather than quietly dropping a column.
    """
    out: dict[str, dict[str, Value]] = {unit.geoid: {} for unit in units}

    # The HUD key is checked FIRST, before any work. It used to be checked after
    # the ZORI pass, which meant a missing key for the cross-check source threw
    # away the primary rent data that needs no key at all, and handed the rent
    # pillar's whole weight to the other pillars. Fail before, not after.
    token = require_key("HUD_API_KEY", HUD_KEY_HELP)

    # ---------------------------------------------------------------- ZORI
    weights_by_unit = {unit.geoid: _collapse_weights(unit.zctas) for unit in units}
    wanted = {zcta for pairs in weights_by_unit.values() for zcta, _ in pairs}

    response = _fetch_zori(ctx)
    months, series = parse_zori_csv(response.text, wanted=wanted)
    retrieved_at = response.retrieved_at
    file_latest = months[-1]
    by_year_month = {(d.year, d.month): d for d in months}
    file_vintage = (
        f"Zillow ZORI, smoothed, all homes plus multifamily, ZIP level, "
        f"file through {_month_label(file_latest)}"
    )
    ctx.log(
        f"ZORI: {len(months)} months through {_month_label(file_latest)}, "
        f"{len(series)} of {len(wanted)} requested ZCTAs present"
    )

    for unit in units:
        weights = weights_by_unit[unit.geoid]
        values = out[unit.geoid]
        total_weight = sum(weight for _, weight in weights)

        if not weights or total_weight <= 0:
            reason = (
                "no ZCTA crosswalk for this submarket; run the Census ZCTA "
                "relationship step before the rent step"
            )
            for key in ("zori_latest", "zori_yoy", "zori_cagr_3y", "zori_month",
                        "zori_zip_coverage", "zori_zips_used"):
                values[key] = _zori_missing(
                    reason, vintage=file_vintage, retrieved_at=retrieved_at
                )
            continue

        # The latest month for a submarket is the most recent month in which
        # any of its ZCTAs has a value. Zillow's per-ZIP series do not all end
        # on the same month, so the file's last column is not always populated
        # for this unit. Coverage is reported at whichever month we land on, so
        # a thin tail shows up in zori_zip_coverage instead of hiding.
        latest_month: date | None = None
        latest_value: float | None = None
        covered = 0.0
        used: list[str] = []
        for month in reversed(months):
            value, month_covered, month_used = _weighted_month(series, weights, month)
            if value is not None:
                latest_month = month
                latest_value = value
                covered = month_covered
                used = month_used
                break

        if latest_month is None:
            reason = (
                f"Zillow publishes no ZORI series for any of the "
                f"{len(weights)} ZCTAs overlapping this submarket "
                f"({', '.join(z for z, _ in weights)}); small ZIPs are "
                f"suppressed for sample size"
            )
            for key in ("zori_latest", "zori_yoy", "zori_cagr_3y", "zori_month",
                        "zori_zip_coverage", "zori_zips_used"):
                values[key] = _zori_missing(
                    reason, vintage=file_vintage, retrieved_at=retrieved_at
                )
            continue

        coverage = covered / total_weight
        month_label = _month_label(latest_month)
        vintage = (
            f"Zillow ZORI, smoothed, all homes plus multifamily, ZIP level, "
            f"{month_label}"
        )

        def _context(value: Any) -> Value:
            return Value(
                value,
                source=SOURCE_NAME,
                vintage=vintage,
                url=ZORI_URL,
                retrieved_at=retrieved_at,
                notes=ZORI_NOTES,
            )

        values["zori_month"] = _context(month_label)
        values["zori_zip_coverage"] = _context(round(coverage, 4))
        values["zori_zips_used"] = _context(",".join(sorted(used)))

        if coverage < MIN_ZIP_COVERAGE:
            # One covered ZIP out of five is not the rent in this submarket.
            reason = (
                f"ZORI covers only {coverage * 100:.0f}% of this submarket by "
                f"area; too thin to use"
            )
            for key in ("zori_latest", "zori_yoy", "zori_cagr_3y"):
                values[key] = _zori_missing(
                    reason, vintage=vintage, retrieved_at=retrieved_at
                )
            continue

        values["zori_latest"] = Value(
            round(latest_value, 2),
            source=SOURCE_NAME,
            vintage=vintage,
            url=ZORI_URL,
            retrieved_at=retrieved_at,
            notes=(
                f"{ZORI_NOTES} Weighted across {len(used)} ZCTA(s) covering "
                f"{coverage * 100:.0f}% of the submarket by area."
            ),
        )

        # Growth windows. Each window gets its own basket and its own
        # renormalised weights, so a ZIP that Zillow only started publishing
        # last year cannot contaminate the 3 year number.
        for key, years, label in (
            ("zori_yoy", 1, "year on year"),
            ("zori_cagr_3y", 3, "3 year"),
        ):
            start_month = by_year_month.get(
                (latest_month.year - years, latest_month.month)
            )
            if start_month is None:
                values[key] = _zori_missing(
                    f"ZORI file has no {latest_month.month:02d} column "
                    f"{years} year(s) before {month_label}, so the {label} "
                    f"window cannot be closed",
                    vintage=vintage,
                    retrieved_at=retrieved_at,
                )
                continue

            window = _weighted_window(series, weights, start_month, latest_month)
            if window is None:
                values[key] = _zori_missing(
                    f"no ZCTA in this submarket has ZORI data at both "
                    f"{_month_label(start_month)} and {month_label}, so the "
                    f"{label} window cannot be closed",
                    vintage=vintage,
                    retrieved_at=retrieved_at,
                )
                continue

            start_value, end_value, window_weight, basket = window
            window_coverage = window_weight / total_weight
            if window_coverage < MIN_ZIP_COVERAGE:
                values[key] = _zori_missing(
                    f"ZORI covers only {window_coverage * 100:.0f}% of this "
                    f"submarket by area across the {label} window; too thin "
                    f"to use",
                    vintage=vintage,
                    retrieved_at=retrieved_at,
                )
                continue
            if start_value <= 0:
                values[key] = _zori_missing(
                    f"ZORI base value at {_month_label(start_month)} is not "
                    f"positive, so a {label} growth rate is undefined",
                    vintage=vintage,
                    retrieved_at=retrieved_at,
                )
                continue

            if years == 1:
                growth = (end_value / start_value - 1.0) * 100.0
            else:
                growth = ((end_value / start_value) ** (1.0 / years) - 1.0) * 100.0

            values[key] = Value(
                round(growth, 3),
                source=SOURCE_NAME,
                vintage=(
                    f"Zillow ZORI, {_month_label(start_month)} to {month_label}"
                ),
                url=ZORI_URL,
                retrieved_at=retrieved_at,
                notes=(
                    f"{ZORI_NOTES} Growth taken on the weighted series, not as "
                    f"an average of per-ZIP growth rates. Basket held fixed at "
                    f"the {len(basket)} ZCTA(s) with data at both "
                    f"{_month_label(start_month)} and {month_label}, covering "
                    f"{window_coverage * 100:.0f}% of the submarket by area."
                ),
            )

    # ----------------------------------------------------------------- FMR
    # token was obtained at the top of this function, before any download.

    fmr_by_county: dict[str, dict[str, Any]] = {}
    for unit in units:
        values = out[unit.geoid]
        county = (unit.county_fips or "").strip()
        if len(county) != 5 or not county.isdigit():
            reason = (
                f"unit {unit.geoid} has no usable 5 digit county FIPS "
                f"('{unit.county_fips}'), so the HUD county entity id cannot "
                f"be built"
            )
            values["fmr_2br"] = _fmr_missing(reason)
            values["fmr_year"] = _fmr_missing(reason)
            values["zori_vs_fmr_ratio"] = _fmr_missing(reason)
            continue

        if county not in fmr_by_county:
            fmr_by_county[county] = _fetch_fmr_for_county(ctx, county, token)
            found = fmr_by_county[county]
            ctx.log(
                f"HUD FMR {county}: "
                + (
                    f"2BR {found['value']:.0f} for FY{found['year']}"
                    if found["value"] is not None
                    else f"missing ({found['reason'][:80]})"
                )
            )
        found = fmr_by_county[county]

        vintage = f"HUD FMR FY{found['year']}" if found["year"] else "HUD FMR"
        notes = FMR_NOTES + (f" {found['shape']}" if found["shape"] else "")

        if found["value"] is None:
            values["fmr_2br"] = _fmr_missing(
                found["reason"], url=found["url"], vintage=vintage,
                retrieved_at=found["retrieved_at"],
            )
            values["fmr_2br"].notes = notes
            values["fmr_year"] = _fmr_missing(
                found["reason"], url=found["url"], vintage=vintage,
                retrieved_at=found["retrieved_at"],
            )
            values["fmr_year"].notes = notes
            values["zori_vs_fmr_ratio"] = _fmr_missing(
                f"no HUD FMR to compare against ({found['reason']})",
                url=found["url"], vintage=vintage,
                retrieved_at=found["retrieved_at"],
            )
            values["zori_vs_fmr_ratio"].notes = ZORI_NOTES + " " + notes
            continue

        values["fmr_2br"] = Value(
            round(found["value"], 2),
            source="HUD User Fair Market Rents API",
            vintage=vintage,
            url=found["url"],
            retrieved_at=found["retrieved_at"],
            notes=notes,
        )
        values["fmr_year"] = Value(
            found["year"],
            source="HUD User Fair Market Rents API",
            vintage=vintage,
            url=found["url"],
            retrieved_at=found["retrieved_at"],
            notes=notes,
        )

        zori_latest = values.get("zori_latest")
        if zori_latest is None or zori_latest.is_missing:
            reason = (
                "no ZORI level for this submarket, so the cross-check ratio "
                "cannot be formed"
            )
            values["zori_vs_fmr_ratio"] = _fmr_missing(
                reason, url=found["url"], vintage=vintage,
                retrieved_at=found["retrieved_at"],
            )
            values["zori_vs_fmr_ratio"].notes = ZORI_NOTES + " " + notes
        elif found["value"] <= 0:
            values["zori_vs_fmr_ratio"] = _fmr_missing(
                "HUD FMR is not positive, so the cross-check ratio is "
                "undefined",
                url=found["url"], vintage=vintage,
                retrieved_at=found["retrieved_at"],
            )
            values["zori_vs_fmr_ratio"].notes = ZORI_NOTES + " " + notes
        else:
            values["zori_vs_fmr_ratio"] = Value(
                round(zori_latest.value / found["value"], 4),
                source=f"{SOURCE_NAME} / HUD User Fair Market Rents API",
                vintage=f"{values['zori_latest'].vintage} vs {vintage}",
                url=found["url"],
                retrieved_at=found["retrieved_at"],
                notes=(
                    ZORI_NOTES
                    + " "
                    + notes
                    + " The two are built on different definitions, so treat "
                    "this only as a sanity check on the ZIP aggregation."
                ),
            )

    # Rule 4: every unit appears with every key, missing or not. Every branch
    # above already fills all nine columns, so this is a belt and braces guard
    # against a future edit opening a path that does not.
    _fmr_keys = {"fmr_2br", "fmr_year", "zori_vs_fmr_ratio"}
    for unit in units:
        for key in _ALL_KEYS:
            if key in out[unit.geoid]:
                continue
            reason = f"'{key}' was not produced by this run"
            out[unit.geoid][key] = (
                _fmr_missing(reason) if key in _fmr_keys else _zori_missing(reason)
            )
    return out
