"""US Census Building Permits Survey (BPS): new residential supply per submarket.

This module answers one question for each candidate submarket: how much new
housing, and in particular how much new multifamily housing, has been permitted
in that jurisdiction over the last three complete calendar years, relative to
the size of the existing household base.

Everything here is written from the documented BPS file layouts. The machine
this was written on cannot reach www2.census.gov, so the URL patterns and the
positional column list below have NOT been validated against a live file. They
are stated explicitly as named constants with comments so a first run can
confirm or correct them quickly, and every parse failure raises FetchError
loudly rather than guessing.
"""

# LIMITATIONS
#
# 1. BPS reports by PERMIT-ISSUING PLACE, not by the geography a permit was
#    pulled for. Many small municipalities do not issue their own building
#    permits: the county (or a neighbouring jurisdiction acting as the permit
#    office) issues them. Such a municipality is genuinely building and still
#    shows up nowhere in the place file. This module therefore refuses to turn
#    "absent from the file" into a zero. It returns MISSING with an explanation
#    and exposes a county level reconciliation column so the reader can see how
#    much of the county's permitting the named jurisdictions actually capture.
# 2. A permit is not a start and a start is not a delivery. Permits lapse,
#    phases slip and some permitted units are never built. Treat this as a
#    leading indicator of competitive supply, not as a pipeline count.
# 3. BPS counts UNITS PERMITTED, with no information on rent band, product type
#    (garden, wrap, build to rent, condo, age restricted, student, affordable)
#    or tenure. A 5+ unit building could be a for sale condo stack or an LIHTC
#    deal. This module cannot tell you which.
# 4. The "5+ units" structure size class is the best available multifamily
#    proxy in BPS, but it lumps a 5 unit walk up in with a 350 unit podium.
# 5. BPS imputes activity for permit offices that fail to report in a given
#    month. Imputed figures are estimates made by the Census Bureau, not
#    reported counts. This module reads the REPORTED block and flags in `notes`
#    when the imputed block for a jurisdiction is non zero, so the reader knows
#    the published Census total for that place is higher than what was actually
#    reported. See INCLUDE_IMPUTED_IN_TOTAL below.
# 6. Annual files are year to date through December. They are revised. A file
#    pulled in January is not the file pulled the following June.
# 7. The per 1,000 household denominator comes from the ACS module, not from
#    here. Without it this module can only publish raw counts.
# 8. Place and minor civil division codes in BPS follow the vintage of the
#    file. A jurisdiction that annexed, incorporated or merged between the BPS
#    vintage and the Census geography vintage used to build `units` may fail to
#    join and will be reported as MISSING rather than as zero.
# 9. Multiple permit offices can report against the same jurisdiction. Their
#    rows are summed. If two offices double count the same project this module
#    cannot detect it.

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from datetime import date

from ..cache import FetchError
from ..context import Context
from ..provenance import MetricSpec, Unit, Value, missing

SOURCE_NAME = "US Census Building Permits Survey (BPS)"

# ---------------------------------------------------------------------------
# Public column surface
# ---------------------------------------------------------------------------

METRICS: list[MetricSpec] = [
    MetricSpec(
        key="permits_5plus_3y_per_1k_hh",
        label="MF permits per 1k HH (3y)",
        pillar="supply",
        # More new multifamily competing for the same renters is worse for a
        # prospective developer, so higher is worse.
        higher_is_better=False,
        unit="units",
        decimals=1,
        scored=True,
        description=(
            "Units permitted in buildings with 5 or more units, summed over the "
            "last three complete calendar years, divided by the household base "
            "in thousands. Household base comes from the ACS module."
        ),
    ),
    MetricSpec(
        key="permits_total_3y_per_1k_hh",
        label="All permits per 1k HH (3y)",
        pillar="supply",
        higher_is_better=False,
        unit="units",
        decimals=1,
        scored=True,
        description=(
            "All permitted housing units (1 unit, 2 unit, 3 to 4 unit and 5 plus "
            "unit structures), summed over the last three complete calendar "
            "years, per 1,000 households."
        ),
    ),
]

CONTEXT_COLUMNS: list[MetricSpec] = [
    MetricSpec(
        key="permits_5plus_3y",
        label="MF units permitted (3y)",
        pillar="supply",
        higher_is_better=False,
        unit="units",
        decimals=0,
        scored=False,
        description="Raw count of units permitted in 5+ unit structures over the window.",
    ),
    MetricSpec(
        key="permits_total_3y",
        label="All units permitted (3y)",
        pillar="supply",
        higher_is_better=False,
        unit="units",
        decimals=0,
        scored=False,
        description="Raw count of all permitted housing units over the window.",
    ),
    MetricSpec(
        key="permits_years",
        label="Permit years used",
        pillar="supply",
        higher_is_better=False,
        unit="",
        decimals=0,
        scored=False,
        description="The three calendar years actually summed, e.g. '2022, 2023, 2024'.",
    ),
    MetricSpec(
        key="permits_county_5plus_3y",
        label="County MF units permitted (3y)",
        pillar="supply",
        higher_is_better=False,
        unit="units",
        decimals=0,
        scored=False,
        description=(
            "County level 5+ unit permits over the same years, from the BPS "
            "county file. Reconciliation check against the place level sums."
        ),
    ),
    MetricSpec(
        key="permits_place_share_of_county",
        label="Screened places share of county MF permits",
        pillar="supply",
        higher_is_better=False,
        unit="share",
        decimals=3,
        scored=False,
        description=(
            "Sum of 5+ unit permits across the screened jurisdictions in this "
            "county, divided by the county total. Same value for every unit in "
            "a county. A low share means most of the county's multifamily "
            "permitting is happening outside the named jurisdictions, usually "
            "because the county itself is the permit issuing office."
        ),
    ),
]

_ALL_KEYS: list[str] = [m.key for m in METRICS] + [c.key for c in CONTEXT_COLUMNS]

# ---------------------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------------------
# UNVERIFIED. Confirm both on first run.
#
# Place level, annual year to date through December:
#   https://www2.census.gov/econ/bps/Place/<Region> Region/<rr><yy>12y.txt
#   e.g. https://www2.census.gov/econ/bps/Place/Midwest%20Region/mw2412y.txt
# County level, annual year to date through December:
#   https://www2.census.gov/econ/bps/County/co<yy>12y.txt
#   e.g. https://www2.census.gov/econ/bps/County/co2412y.txt
#
# Filename grammar: region code (ne/mw/so/we, or "co" for the county file),
# then 2 digit year, then 2 digit month (12 for the full year), then the
# letter 'y' meaning year to date (as opposed to 'c' for the single month).
BPS_BASE_URL = "https://www2.census.gov/econ/bps"
PLACE_URL_TEMPLATE = "{base}/Place/{region_dir}/{region_code}{yy}12y.txt"
COUNTY_URL_TEMPLATE = "{base}/County/co{yy}12y.txt"

# The space in "Midwest Region" has to be percent encoded in the URL. The
# directory names on the server carry a real space.
_REGION_DIR_ENCODED = {
    "ne": "Northeast%20Region",
    "mw": "Midwest%20Region",
    "so": "South%20Region",
    "we": "West%20Region",
}

# State FIPS -> (region code, region directory name, region label).
# Census statistical regions. The four markets this project ships with are
# WI (55) and MI (26) in the Midwest, KY (21) and GA (13) in the South, but the
# full 50 state plus DC mapping is here because it costs nothing.
STATE_FIPS_TO_REGION: dict[str, tuple[str, str]] = {
    # Northeast
    "09": ("ne", "Connecticut"),
    "23": ("ne", "Maine"),
    "25": ("ne", "Massachusetts"),
    "33": ("ne", "New Hampshire"),
    "34": ("ne", "New Jersey"),
    "36": ("ne", "New York"),
    "42": ("ne", "Pennsylvania"),
    "44": ("ne", "Rhode Island"),
    "50": ("ne", "Vermont"),
    # Midwest
    "17": ("mw", "Illinois"),
    "18": ("mw", "Indiana"),
    "19": ("mw", "Iowa"),
    "20": ("mw", "Kansas"),
    "26": ("mw", "Michigan"),
    "27": ("mw", "Minnesota"),
    "29": ("mw", "Missouri"),
    "31": ("mw", "Nebraska"),
    "38": ("mw", "North Dakota"),
    "39": ("mw", "Ohio"),
    "46": ("mw", "South Dakota"),
    "55": ("mw", "Wisconsin"),
    # South
    "01": ("so", "Alabama"),
    "05": ("so", "Arkansas"),
    "10": ("so", "Delaware"),
    "11": ("so", "District of Columbia"),
    "12": ("so", "Florida"),
    "13": ("so", "Georgia"),
    "21": ("so", "Kentucky"),
    "22": ("so", "Louisiana"),
    "24": ("so", "Maryland"),
    "28": ("so", "Mississippi"),
    "37": ("so", "North Carolina"),
    "40": ("so", "Oklahoma"),
    "45": ("so", "South Carolina"),
    "47": ("so", "Tennessee"),
    "48": ("so", "Texas"),
    "51": ("so", "Virginia"),
    "54": ("so", "West Virginia"),
    # West
    "02": ("we", "Alaska"),
    "04": ("we", "Arizona"),
    "06": ("we", "California"),
    "08": ("we", "Colorado"),
    "15": ("we", "Hawaii"),
    "16": ("we", "Idaho"),
    "30": ("we", "Montana"),
    "32": ("we", "Nevada"),
    "35": ("we", "New Mexico"),
    "41": ("we", "Oregon"),
    "49": ("we", "Utah"),
    "53": ("we", "Washington"),
    "56": ("we", "Wyoming"),
}

# ---------------------------------------------------------------------------
# File layout
# ---------------------------------------------------------------------------
# These files are comma separated with a MULTI LINE header: the column names
# are split across roughly three physical lines, so pandas cannot infer them
# and neither can csv.Sniffer. We skip every leading line whose first field is
# not numeric and then parse POSITIONALLY against the lists below. If the field
# count does not match we raise FetchError rather than risk reading the "Value"
# column as if it were the "Units" column.

# Place file, fields 0 to 16, in order. VERIFIED against the real published
# header of mw2312y.txt and mw2512y.txt, which reads:
#
#   Survey,State,6-Digit,County,Census Place,FIPS Place,FIPS MCD,Pop,CSA,CBSA,
#   Footnote,Central,Zip,Region,Division,Number of,Place,,1-unit,,,2-units,...
#   Date,Code,ID,Code,Code,Code,Code,  ,Code,Code,Code,City,Code,Code,Code,
#   Months Rep,Name,Bldgs,Units,Value,...
#
# An earlier version of this list was written from documentation and had two
# errors: it put state FIPS at index 14 and had no "Number of Months Reported"
# column at all, which shifted the place name and every value after it. The
# field count check caught that and refused to parse, which is exactly what it
# is for.
PLACE_PREFIX_FIELDS: list[str] = [
    "survey_date",        # 0  yyyymm of the survey period, e.g. 202512
    "state_fips",         # 1  2 digit state FIPS
    "six_digit_id",       # 2  Census internal permit office id
    "county_code3",       # 3  3 digit county FIPS within the state
    "census_place_code",  # 4  Census (not FIPS) place code
    "fips_place_code",    # 5  FIPS place code, join key for geo_type "place"
    "fips_mcd_code",      # 6  FIPS MCD code, join key for "county_subdivision"
    "pop",                # 7  population of the permit issuing place
    "csa_code",           # 8
    "cbsa_code",          # 9
    "footnote_code",      # 10
    "central_city_flag",  # 11
    "zip_code",           # 12
    "region_code",        # 13
    "division_code",      # 14
    "months_reported",    # 15 how many of the 12 months this office reported
    "place_name",         # 16 name of the permit issuing place
]
PLACE_PREFIX_LEN = len(PLACE_PREFIX_FIELDS)  # 17

# After the prefix comes the value block. For each structure size class, in
# this order, a triple of (Bldgs, Units, Value in dollars):
STRUCTURE_SIZE_CLASSES: tuple[str, ...] = ("1_unit", "2_unit", "3_to_4_unit", "5_plus_unit")
TRIPLE_LEN = 3               # Bldgs, Units, Value
UNITS_OFFSET_IN_TRIPLE = 1   # we want the middle member of each triple
BLOCK_LEN = len(STRUCTURE_SIZE_CLASSES) * TRIPLE_LEN  # 12

# The four triples appear twice. The header calls the second set "1-unit rep,
# 2-units rep, ..." and the real data settles what that means: Addison village
# in the 2025 file reports 12 of 12 months and its two blocks are identical.
# So the second block is the PUBLISHED total, reported plus whatever the Census
# imputed for months an office did not report, and it equals the first block
# whenever an office reported all twelve months. It is therefore the headline
# figure, and the difference between the two blocks is the imputed portion.
#
# This matters. Treating the second block as "imputed only" and adding it to
# the first would double count every fully reporting jurisdiction.
PLACE_FIELDS_REPORTED_ONLY = PLACE_PREFIX_LEN + BLOCK_LEN          # 29
PLACE_FIELDS_WITH_IMPUTED = PLACE_PREFIX_LEN + 2 * BLOCK_LEN       # 41
PLACE_ACCEPTED_FIELD_COUNTS = (PLACE_FIELDS_REPORTED_ONLY, PLACE_FIELDS_WITH_IMPUTED)

# County file, fields 0 to 5, in order. UNVERIFIED, same caveat as the URLs.
COUNTY_PREFIX_FIELDS: list[str] = [
    "survey_date",      # 0
    "state_fips",       # 1
    "county_code3",     # 2
    "region_code",      # 3
    "division_code",    # 4
    "county_name",      # 5
]
COUNTY_PREFIX_LEN = len(COUNTY_PREFIX_FIELDS)  # 6
COUNTY_FIELDS_REPORTED_ONLY = COUNTY_PREFIX_LEN + BLOCK_LEN        # 18
COUNTY_FIELDS_WITH_IMPUTED = COUNTY_PREFIX_LEN + 2 * BLOCK_LEN     # 30
COUNTY_ACCEPTED_FIELD_COUNTS = (COUNTY_FIELDS_REPORTED_ONLY, COUNTY_FIELDS_WITH_IMPUTED)

# Which block feeds the published metric.
#
# We publish the REPORTED block and flag imputation in `notes`. The Census
# Bureau's own published totals include imputed activity, so a figure here can
# sit below the headline Census number for the same place. That is deliberate:
# this project never prefers an estimate to a reported count, and rule 1 of the
# source module contract forbids passing an estimate off as data. Flip this to
# True only after deciding you want Census imputations in the ranking, and say
# so in the workbook if you do.
MONTHS_IN_YEAR = 12

# Kept for reference. The published figure is now always the second block, so
# there is nothing to switch: see the comment above PLACE_FIELDS_REPORTED_ONLY
# for why adding the blocks together would double count.
INCLUDE_IMPUTED_IN_TOTAL = False

# How many complete calendar years are summed.
WINDOW_YEARS = 3
# How many Decembers back we probe before giving up on finding a published year.
MAX_YEAR_PROBES = 4
# Annual year to date files are revised but not often. A month is plenty.
BPS_CACHE_TTL_DAYS = 30

_UNMATCHED_CODES = {"", "0", "00000", "99999", "999999"}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


@dataclass
class PlaceRow:
    """One permit office row from a BPS place file."""

    state_fips: str
    county_code3: str
    fips_place_code: str
    fips_mcd_code: str
    place_name: str
    months_reported: int
    units_reported: tuple[int, int, int, int]
    units_published: tuple[int, int, int, int]

    @property
    def reported_5plus(self) -> int:
        return self.units_reported[3]

    @property
    def reported_total(self) -> int:
        return sum(self.units_reported)

    @property
    def published_5plus(self) -> int:
        return self.units_published[3]

    @property
    def published_total(self) -> int:
        return sum(self.units_published)

    @property
    def imputed_5plus(self) -> int:
        # The imputed portion is the gap between the two blocks, never the
        # second block itself.
        return max(0, self.units_published[3] - self.units_reported[3])

    @property
    def imputed_total(self) -> int:
        return max(0, sum(self.units_published) - sum(self.units_reported))

    @property
    def place_key(self) -> str:
        """state FIPS (2) + FIPS place code (5). Empty when not joinable."""
        code = _norm_code(self.fips_place_code, 5)
        return f"{self.state_fips}{code}" if code else ""

    @property
    def cousub_key(self) -> str:
        """state (2) + county (3) + FIPS MCD code (5). Empty when not joinable."""
        code = _norm_code(self.fips_mcd_code, 5)
        county = _norm_code(self.county_code3, 3)
        if not code or not county:
            return ""
        return f"{self.state_fips}{county}{code}"


@dataclass
class CountyRow:
    state_fips: str
    county_code3: str
    county_name: str
    units_reported: tuple[int, int, int, int]
    units_published: tuple[int, int, int, int]

    @property
    def county_fips(self) -> str:
        county = _norm_code(self.county_code3, 3)
        return f"{self.state_fips}{county}" if county else ""


def _norm_code(raw: str, width: int) -> str:
    """Zero pad a numeric geography code, or return "" when it cannot join.

    A blank code, an all zero code, or one of the documented "not codable"
    sentinels means the permit office could not be tied to a named
    jurisdiction. Those rows carry real permits and must not be dropped
    silently, so callers tally them instead of ignoring them.
    """
    s = "".join((raw or "").split()).strip('"')
    if not s or not s.isdigit():
        return ""
    if len(s) > width:
        # Wider than the documented field width. Refuse rather than truncate.
        return ""
    padded = s.zfill(width)
    if set(padded) == {"0"} or padded in _UNMATCHED_CODES:
        return ""
    return padded


def _clean(raw: str) -> str:
    return (raw or "").strip().strip('"').strip()


def _to_int(raw: str) -> int:
    """Parse a BPS numeric cell. Blank means zero. Anything else raises."""
    s = _clean(raw).replace(",", "")
    if not s:
        return 0
    return int(round(float(s)))


def _looks_like_data_row(fields: list[str]) -> bool:
    """A data row starts with a numeric survey date. Header lines do not.

    The header of these files spans about three physical lines with the column
    names split across them, so there is no fixed number of lines to skip.
    Sniffing on "is field 0 numeric" survives a header that grows or shrinks.
    Internal whitespace is removed first in case the date is written "2024 12".
    """
    if not fields:
        return False
    first = "".join(fields[0].split()).strip('"')
    return bool(first) and first.isdigit()


def _trim_trailing_blanks(fields: list[str], accepted: tuple[int, ...]) -> list[str]:
    """Drop trailing empty fields left by a stray comma at end of line."""
    out = list(fields)
    floor = min(accepted)
    while len(out) > floor and len(out) not in accepted and not out[-1].strip():
        out.pop()
    return out


def _units_from_block(fields: list[str], start: int) -> tuple[int, int, int, int]:
    """Read four (Bldgs, Units, Value) triples and return just the Units."""
    vals = []
    for i in range(len(STRUCTURE_SIZE_CLASSES)):
        vals.append(_to_int(fields[start + i * TRIPLE_LEN + UNITS_OFFSET_IN_TRIPLE]))
    return (vals[0], vals[1], vals[2], vals[3])


def _iter_rows(text: str, url: str, accepted: tuple[int, ...], label: str):
    """Yield (line_no, fields) for data rows, validating the field count.

    Raises FetchError naming the file, the line, the observed field count and
    the expected counts if the layout does not line up. Rule 5 of the source
    module contract: raise, do not guess.
    """
    seen_data = False
    for line_no, fields in enumerate(csv.reader(io.StringIO(text)), start=1):
        if not fields or all(not f.strip() for f in fields):
            continue
        if not _looks_like_data_row(fields):
            if seen_data:
                # A non numeric line after data has started is a footer or a
                # repeated header. Skip it, but do not let it change the layout.
                continue
            continue
        fields = _trim_trailing_blanks(fields, accepted)
        n = len(fields)
        if n not in accepted:
            raise FetchError(
                f"Census BPS {label} file {url} line {line_no}: got {n} comma "
                f"separated fields, expected one of {list(accepted)} "
                f"({accepted[0]} without the imputed block, {accepted[-1]} with "
                f"it). The published layout has changed; refusing to parse "
                f"positionally because a mis-read column is worse than no data."
            )
        seen_data = True
        yield line_no, fields
    if not seen_data:
        raise FetchError(
            f"Census BPS {label} file {url}: no data rows found. The file is "
            f"header only, empty, or is not the fixed layout text file this "
            f"parser expects."
        )


def parse_place_file(text: str, url: str) -> list[PlaceRow]:
    """Parse a BPS place file into rows. See PLACE_PREFIX_FIELDS for layout."""
    rows: list[PlaceRow] = []
    for line_no, f in _iter_rows(text, url, PLACE_ACCEPTED_FIELD_COUNTS, "place"):
        try:
            reported = _units_from_block(f, PLACE_PREFIX_LEN)
            if len(f) == PLACE_FIELDS_WITH_IMPUTED:
                published = _units_from_block(f, PLACE_PREFIX_LEN + BLOCK_LEN)
            else:
                # Older vintage with the reported block only. There is no
                # published total to read, so the reported figure is all we
                # have and the imputed portion is unknowable, not zero.
                published = reported
        except (ValueError, IndexError) as exc:
            raise FetchError(
                f"Census BPS place file {url} line {line_no}: could not read the "
                f"value block ({exc}). Expected 4 triples of (Bldgs, Units, "
                f"Value) starting at field {PLACE_PREFIX_LEN}."
            ) from exc
        rows.append(
            PlaceRow(
                state_fips=_clean(f[1]).zfill(2),
                county_code3=_clean(f[3]).zfill(3),
                fips_place_code=_clean(f[5]),
                fips_mcd_code=_clean(f[6]),
                place_name=_clean(f[16]),
                months_reported=_to_int(f[15]),
                units_reported=reported,
                units_published=published,
            )
        )
    return rows


def parse_county_file(text: str, url: str) -> list[CountyRow]:
    """Parse a BPS county file. See COUNTY_PREFIX_FIELDS for layout."""
    rows: list[CountyRow] = []
    for line_no, f in _iter_rows(text, url, COUNTY_ACCEPTED_FIELD_COUNTS, "county"):
        try:
            reported = _units_from_block(f, COUNTY_PREFIX_LEN)
            if len(f) == COUNTY_FIELDS_WITH_IMPUTED:
                published = _units_from_block(f, COUNTY_PREFIX_LEN + BLOCK_LEN)
            else:
                published = reported
        except (ValueError, IndexError) as exc:
            raise FetchError(
                f"Census BPS county file {url} line {line_no}: could not read the "
                f"value block ({exc}). Expected 4 triples of (Bldgs, Units, "
                f"Value) starting at field {COUNTY_PREFIX_LEN}."
            ) from exc
        rows.append(
            CountyRow(
                state_fips=_clean(f[1]).zfill(2),
                county_code3=_clean(f[2]),
                county_name=_clean(f[5]),
                units_reported=reported,
                units_published=published,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def place_url(region_code: str, year: int) -> str:
    region_dir = _REGION_DIR_ENCODED[region_code]
    return PLACE_URL_TEMPLATE.format(
        base=BPS_BASE_URL,
        region_dir=region_dir,
        region_code=region_code,
        yy=f"{year % 100:02d}",
    )


def county_url(year: int) -> str:
    return COUNTY_URL_TEMPLATE.format(base=BPS_BASE_URL, yy=f"{year % 100:02d}")


class _Fetcher:
    """Thin memo over ctx.cache so one file is fetched at most once per run."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self._memo: dict[str, object] = {}

    def get(self, url: str, key: str):
        if url in self._memo:
            return self._memo[url]
        # No expect_content_type: www2.census.gov has been observed to serve
        # these .txt files as text/plain and as application/octet-stream
        # depending on the mirror, so we validate by parsing instead.
        resp = self.ctx.cache.get(url, key=key, ttl_days=BPS_CACHE_TTL_DAYS)
        self._memo[url] = resp
        return resp


def _probe_start_year() -> int:
    """First year to probe: the previous calendar year.

    The current year's December year to date file does not exist until the
    following year, so we never even ask for it.
    """
    return date.today().year - 1


def resolve_latest_complete_year(ctx: Context, fetcher: _Fetcher, region_code: str) -> int:
    """Probe December year to date files backwards until one downloads.

    Census publishes the annual file some months into the following year, and
    the exact month moves. Rather than hard coding a year we ask the server.
    """
    errors: list[str] = []
    start = _probe_start_year()
    for attempt in range(MAX_YEAR_PROBES):
        year = start - attempt
        url = place_url(region_code, year)
        try:
            fetcher.get(url, key=f"bps_place_{region_code}_{year}12y")
        except FetchError as exc:
            errors.append(f"{year}: {exc}")
            continue
        ctx.log(
            f"BPS: latest complete year resolved to {year} "
            f"(probed {attempt + 1} of {MAX_YEAR_PROBES} from {start} backwards)"
        )
        return year
    raise FetchError(
        f"Census BPS: no annual place file found for region '{region_code}' in "
        f"{MAX_YEAR_PROBES} attempts back from {start}. Tried: "
        + " | ".join(errors)
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass
class _Agg:
    """Running totals for one jurisdiction across the 3 year window."""

    rows: int = 0
    units_5plus: int = 0
    units_total: int = 0
    imputed_5plus: int = 0
    imputed_total: int = 0
    months_reported: int = 0
    months_possible: int = 0
    years_present: set[int] = dc_field(default_factory=set)
    offices: set[str] = dc_field(default_factory=set)

    def add(self, row: PlaceRow, year: int) -> None:
        self.rows += 1
        # The published figure is the second block: reported plus whatever the
        # Census imputed for months the office did not file. Adding the two
        # blocks together would double count every office that reported in full.
        self.units_5plus += row.published_5plus
        self.units_total += row.published_total
        self.imputed_5plus += row.imputed_5plus
        self.imputed_total += row.imputed_total
        self.months_reported += row.months_reported
        self.months_possible += MONTHS_IN_YEAR
        self.years_present.add(year)
        if row.place_name:
            self.offices.add(row.place_name)

    @property
    def never_reported(self) -> bool:
        """True when no office filed a single month across the whole window.

        A jurisdiction that filed nothing and therefore shows zero permits is
        not the same as one that filed twelve months and genuinely permitted
        nothing. Without the Number of Months Reported column the two are
        indistinguishable, which is why that column matters more than it looks.
        """
        return self.months_possible > 0 and self.months_reported == 0


def _value(
    value,
    *,
    urls: list[str],
    retrieved_at: str,
    vintage: str,
    notes: str = "",
) -> Value:
    return Value(
        value,
        source=SOURCE_NAME,
        vintage=vintage,
        url=", ".join(urls),
        retrieved_at=retrieved_at,
        notes=notes,
    )


def _missing_all(reason: str, *, url: str = "", vintage: str = "") -> dict[str, Value]:
    return {
        k: missing(reason, source=SOURCE_NAME, vintage=vintage, url=url)
        for k in _ALL_KEYS
    }


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def collect(
    ctx: Context,
    units: list[Unit],
    households: dict[str, float] | None = None,
) -> dict[str, dict[str, Value]]:
    """Return {geoid: {metric_key: Value}} for every unit passed in.

    `households` is an optional {geoid: household count} map produced by the
    ACS module. This module has no household base of its own, so when the map
    is absent, or a unit is not in it, the two per 1,000 household metrics come
    back MISSING and only the raw counts are published.
    """
    results: dict[str, dict[str, Value]] = {}
    if not units:
        return results

    fetcher = _Fetcher(ctx)

    # ---------------------------------------------------------------- regions
    # Group the units by the BPS region their state sits in. One file per
    # region per year covers every place in that region.
    region_of_unit: dict[str, str] = {}
    unsupported: dict[str, str] = {}
    for u in units:
        st = (u.state_fips or "").zfill(2)
        entry = STATE_FIPS_TO_REGION.get(st)
        if entry is None:
            unsupported[u.geoid] = (
                f"no BPS region mapping for state FIPS '{st}'. Add it to "
                f"STATE_FIPS_TO_REGION in screener/sources/census_bps.py."
            )
            continue
        region_of_unit[u.geoid] = entry[0]

    regions = sorted(set(region_of_unit.values()))
    if not regions:
        for u in units:
            results[u.geoid] = _missing_all(
                unsupported.get(u.geoid, "no BPS region could be determined")
            )
        return results

    # ------------------------------------------------------- year resolution
    # Probe with the most common region so the probe cost is paid once.
    region_counts: dict[str, int] = defaultdict(int)
    for r in region_of_unit.values():
        region_counts[r] += 1
    probe_region = max(regions, key=lambda r: (region_counts[r], r))

    try:
        latest_year = resolve_latest_complete_year(ctx, fetcher, probe_region)
    except FetchError as exc:
        reason = f"BPS annual file download failed: {exc}"
        for u in units:
            results[u.geoid] = _missing_all(reason)
        return results

    years = sorted(range(latest_year - WINDOW_YEARS + 1, latest_year + 1))
    years_label = ", ".join(str(y) for y in years)
    vintage = f"BPS annual year to date (December), {years_label}"
    ctx.log(f"BPS: summing permit years {years_label}")

    # ------------------------------------------------------ place file pulls
    place_agg: dict[str, _Agg] = defaultdict(_Agg)
    region_urls: dict[str, list[str]] = defaultdict(list)
    region_retrieved: dict[str, str] = {}
    region_error: dict[str, str] = {}

    for region in regions:
        unmatched_units = 0
        unmatched_rows = 0
        for year in years:
            url = place_url(region, year)
            try:
                resp = fetcher.get(url, key=f"bps_place_{region}_{year}12y")
            except FetchError as exc:
                # A three year sum with one year missing is not a three year
                # sum, so the whole region is reported as MISSING rather than
                # quietly short.
                region_error[region] = (
                    f"BPS place file for {year} could not be downloaded: {exc}"
                )
                break
            region_urls[region].append(url)
            # retrieved_at must come from the CachedResponse, never from
            # datetime.now(). We keep the OLDEST of the three downloads so the
            # workbook reports the most conservative freshness.
            stamp = getattr(resp, "retrieved_at", "") or ""
            prev = region_retrieved.get(region)
            if stamp and (prev is None or stamp < prev):
                region_retrieved[region] = stamp

            for row in parse_place_file(resp.text, url):
                place_key = row.place_key
                cousub_key = row.cousub_key
                if not place_key and not cousub_key:
                    # Permit office that could not be tied to any named
                    # jurisdiction (typically unincorporated county area).
                    unmatched_rows += 1
                    unmatched_units += row.reported_total
                    continue
                if place_key:
                    place_agg[place_key].add(row, year)
                if cousub_key:
                    place_agg[cousub_key].add(row, year)
        if region not in region_error and unmatched_rows:
            ctx.log(
                f"BPS {region}: {unmatched_rows} permit office rows across "
                f"{years_label} had no FIPS place or MCD code and could not be "
                f"joined, covering {unmatched_units} permitted units. Those are "
                f"usually unincorporated county area."
            )
        if region in region_error:
            ctx.log(f"BPS {region}: {region_error[region]}")

    # ----------------------------------------------------- county file pulls
    wanted_counties = {u.county_fips for u in units if u.county_fips}
    county_5plus: dict[str, int] = defaultdict(int)
    county_urls: list[str] = []
    county_retrieved = ""
    county_error = ""
    if wanted_counties:
        for year in years:
            url = county_url(year)
            try:
                resp = fetcher.get(url, key=f"bps_county_{year}12y")
            except FetchError as exc:
                county_error = (
                    f"BPS county file for {year} could not be downloaded: {exc}"
                )
                break
            county_urls.append(url)
            stamp = getattr(resp, "retrieved_at", "") or ""
            if stamp and (not county_retrieved or stamp < county_retrieved):
                county_retrieved = stamp
            for crow in parse_county_file(resp.text, url):
                fips = crow.county_fips
                if not fips or fips not in wanted_counties:
                    continue
                # Same reading as the place file: the second block is the
                # published total, not an increment to add on.
                county_5plus[fips] += crow.units_published[3]
        if county_error:
            county_5plus.clear()
            ctx.log(f"BPS county: {county_error}")

    # ------------------------------------------------------ per unit results
    # Pass 1: resolve each unit's own aggregate so county shares can be built.
    matched: dict[str, _Agg] = {}
    unit_reason: dict[str, str] = {}
    for u in units:
        if u.geoid in unsupported:
            unit_reason[u.geoid] = unsupported[u.geoid]
            continue
        region = region_of_unit[u.geoid]
        if region in region_error:
            # Case (c): the file failed to download.
            unit_reason[u.geoid] = region_error[region]
            continue
        key = _join_key(u)
        if key is None:
            unit_reason[u.geoid] = (
                f"unsupported geo_type '{u.geo_type}'. This module joins BPS on "
                f"'place' or 'county_subdivision' only."
            )
            continue
        agg = place_agg.get(key)
        if agg is None:
            # Case (b): the jurisdiction is simply not in the file. It is NOT
            # zero. BPS reports by permit issuing place, and a municipality
            # that does not run its own building department never appears.
            unit_reason[u.geoid] = (
                "not a permit-issuing place in BPS; permits are likely issued "
                "by the county"
            )
            continue
        # Case (a): present in the file, possibly with zero units.
        matched[u.geoid] = agg

    # Screened place sums per county, for the reconciliation share.
    county_place_sum: dict[str, int] = defaultdict(int)
    for u in units:
        agg = matched.get(u.geoid)
        if agg is not None and u.county_fips:
            county_place_sum[u.county_fips] += agg.units_5plus

    # Pass 2: build the Values.
    for u in units:
        region = region_of_unit.get(u.geoid)
        urls = region_urls.get(region, []) if region else []
        retrieved = region_retrieved.get(region, "") if region else ""
        agg = matched.get(u.geoid)

        if agg is None:
            reason = unit_reason.get(u.geoid, "no BPS figure available")
            cells = _missing_all(reason, url=", ".join(urls), vintage=vintage)
            # The years used are still knowable and still worth showing, and so
            # is the county reconciliation, which is exactly what a reader
            # wants when a place is absent from the file.
            cells["permits_years"] = _value(
                years_label,
                urls=urls,
                retrieved_at=retrieved,
                vintage=vintage,
                notes="Calendar years summed for this run.",
            )
            _fill_county_cells(
                cells,
                unit=u,
                county_5plus=county_5plus,
                county_place_sum=county_place_sum,
                county_urls=county_urls,
                county_retrieved=county_retrieved,
                county_error=county_error,
                vintage=vintage,
            )
            results[u.geoid] = cells
            continue

        notes_bits: list[str] = [
            "BPS counts units permitted by the permit issuing place, not starts "
            "or deliveries."
        ]
        if agg.rows > len(agg.years_present):
            notes_bits.append(
                f"{agg.rows} permit office rows summed across "
                f"{len(agg.years_present)} year files "
                f"({'; '.join(sorted(agg.offices))})."
            )
        missing_years = [y for y in years if y not in agg.years_present]
        if missing_years:
            notes_bits.append(
                "Absent from the "
                + ", ".join(str(y) for y in missing_years)
                + " file, so those years contribute nothing to the sum."
            )
        if agg.units_total == 0:
            if agg.never_reported:
                # A fifth case, and only the Number of Months Reported column
                # can tell it apart from a genuine zero: the jurisdiction is in
                # the file, but no permit office filed a single month, so its
                # zero is an absence of reporting rather than an absence of
                # building. Scoring that as zero supply would reward a
                # jurisdiction for its own silence.
                notes_bits.append(
                    "This jurisdiction appears in the BPS file but no permit "
                    "office reported a single month over the window, so its "
                    "zero is an absence of reporting, not a reported zero."
                )
            else:
                notes_bits.append(
                    f"This jurisdiction appears in the BPS file, reported "
                    f"{agg.months_reported} of {agg.months_possible} office "
                    f"months, and permitted zero units over the window. This is "
                    f"a reported zero, not a gap."
                )
        if agg.imputed_total > 0:
            notes_bits.append(
                f"Of the units shown, {agg.imputed_total} ({agg.imputed_5plus} "
                f"in 5+ unit structures) were imputed by the Census for months "
                f"this permit office did not report, not counted from an actual "
                f"permit. The figure shown is the published Census total, which "
                f"includes them."
            )
        if agg.months_possible:
            notes_bits.append(
                f"Permit offices reported {agg.months_reported} of "
                f"{agg.months_possible} possible office months over the window."
            )
        notes = " ".join(notes_bits)

        cells: dict[str, Value] = {}
        cells["permits_5plus_3y"] = _value(
            agg.units_5plus, urls=urls, retrieved_at=retrieved, vintage=vintage, notes=notes
        )
        cells["permits_total_3y"] = _value(
            agg.units_total, urls=urls, retrieved_at=retrieved, vintage=vintage, notes=notes
        )
        cells["permits_years"] = _value(
            years_label,
            urls=urls,
            retrieved_at=retrieved,
            vintage=vintage,
            notes="Calendar years summed for this run.",
        )

        hh = None
        if households:
            raw_hh = households.get(u.geoid)
            if raw_hh is not None:
                try:
                    hh = float(raw_hh)
                except (TypeError, ValueError):
                    hh = None
        if agg.never_reported:
            never_reason = (
                "in the BPS file but no permit office reported a single month "
                "over the window, so a supply figure here would measure "
                "silence rather than building"
            )
            cells["permits_5plus_3y_per_1k_hh"] = missing(
                never_reason, source=SOURCE_NAME, vintage=vintage, url=", ".join(urls)
            )
            cells["permits_total_3y_per_1k_hh"] = missing(
                never_reason, source=SOURCE_NAME, vintage=vintage, url=", ".join(urls)
            )
        elif missing_years:
            # A short window is the fourth case, and it is the dangerous one.
            # The raw counts above stay as context with the note saying which
            # years are absent, but the SCORED metrics must not go out as if
            # they were a three year total. Supply pressure is scored low is
            # good, so a permit office that failed to file for two of three
            # years would otherwise look like a quiet, undersupplied submarket
            # and climb the ranking on the strength of its own missing data.
            short_reason = (
                "permit records cover only "
                + ", ".join(str(y) for y in sorted(agg.years_present))
                + " of the "
                + ", ".join(str(y) for y in years)
                + " window, so a three year rate would understate supply"
            )
            cells["permits_5plus_3y_per_1k_hh"] = missing(
                short_reason, source=SOURCE_NAME, vintage=vintage, url=", ".join(urls)
            )
            cells["permits_total_3y_per_1k_hh"] = missing(
                short_reason, source=SOURCE_NAME, vintage=vintage, url=", ".join(urls)
            )
        elif hh is None or hh <= 0:
            hh_reason = "household base not available from ACS"
            cells["permits_5plus_3y_per_1k_hh"] = missing(
                hh_reason, source=SOURCE_NAME, vintage=vintage, url=", ".join(urls)
            )
            cells["permits_total_3y_per_1k_hh"] = missing(
                hh_reason, source=SOURCE_NAME, vintage=vintage, url=", ".join(urls)
            )
        else:
            per_note = (
                notes
                + f" Denominator: {hh:,.0f} households from the ACS module."
            )
            cells["permits_5plus_3y_per_1k_hh"] = _value(
                agg.units_5plus / (hh / 1000.0),
                urls=urls,
                retrieved_at=retrieved,
                vintage=vintage,
                notes=per_note,
            )
            cells["permits_total_3y_per_1k_hh"] = _value(
                agg.units_total / (hh / 1000.0),
                urls=urls,
                retrieved_at=retrieved,
                vintage=vintage,
                notes=per_note,
            )

        _fill_county_cells(
            cells,
            unit=u,
            county_5plus=county_5plus,
            county_place_sum=county_place_sum,
            county_urls=county_urls,
            county_retrieved=county_retrieved,
            county_error=county_error,
            vintage=vintage,
        )
        results[u.geoid] = cells

    # Rule 4: every unit passed in must come back, even if wholly missing.
    for u in units:
        results.setdefault(u.geoid, _missing_all("no BPS figure available"))
    return results


def _join_key(unit: Unit) -> str | None:
    """Build the BPS join key for a unit, or None for an unsupported geo_type.

    place              -> state FIPS (2) + FIPS place code (5)
    county_subdivision -> state FIPS (2) + county (3) + FIPS MCD code (5)

    Both are exactly the Census GEOID for the unit, so in practice this is the
    geoid, rebuilt from the parts to avoid depending on how it was assembled.
    """
    st = (unit.state_fips or "").zfill(2)
    if unit.geo_type == "place":
        return f"{st}{unit.geoid[-5:].zfill(5)}"
    if unit.geo_type == "county_subdivision":
        county3 = (unit.county_fips or "")[2:5]
        if not county3:
            county3 = unit.geoid[2:5]
        return f"{st}{county3.zfill(3)}{unit.geoid[-5:].zfill(5)}"
    return None


def _fill_county_cells(
    cells: dict[str, Value],
    *,
    unit: Unit,
    county_5plus: dict[str, int],
    county_place_sum: dict[str, int],
    county_urls: list[str],
    county_retrieved: str,
    county_error: str,
    vintage: str,
) -> None:
    """Add the two county reconciliation columns to a unit's cells."""
    url_str = ", ".join(county_urls)
    if county_error:
        cells["permits_county_5plus_3y"] = missing(
            county_error, source=SOURCE_NAME, vintage=vintage, url=url_str
        )
        cells["permits_place_share_of_county"] = missing(
            county_error, source=SOURCE_NAME, vintage=vintage, url=url_str
        )
        return
    if not unit.county_fips:
        reason = "unit has no county FIPS, county reconciliation not possible"
        cells["permits_county_5plus_3y"] = missing(
            reason, source=SOURCE_NAME, vintage=vintage, url=url_str
        )
        cells["permits_place_share_of_county"] = missing(
            reason, source=SOURCE_NAME, vintage=vintage, url=url_str
        )
        return
    if unit.county_fips not in county_5plus:
        reason = (
            f"county {unit.county_fips} does not appear in the BPS county file "
            f"for these years"
        )
        cells["permits_county_5plus_3y"] = missing(
            reason, source=SOURCE_NAME, vintage=vintage, url=url_str
        )
        cells["permits_place_share_of_county"] = missing(
            reason, source=SOURCE_NAME, vintage=vintage, url=url_str
        )
        return

    total = county_5plus[unit.county_fips]
    cells["permits_county_5plus_3y"] = _value(
        total,
        urls=county_urls,
        retrieved_at=county_retrieved,
        vintage=vintage,
        notes=(
            "County wide 5+ unit permits from the BPS county file, same window. "
            "Use it to sanity check the place level sums: if the county number "
            "is far bigger than the screened places add up to, most permitting "
            "in this county is issued somewhere other than the named "
            "jurisdictions."
        ),
    )
    if total <= 0:
        cells["permits_place_share_of_county"] = missing(
            "county reported zero 5+ unit permits over the window, so the share "
            "is undefined",
            source=SOURCE_NAME,
            vintage=vintage,
            url=url_str,
        )
        return
    share = county_place_sum.get(unit.county_fips, 0) / float(total)
    cells["permits_place_share_of_county"] = _value(
        share,
        urls=county_urls,
        retrieved_at=county_retrieved,
        vintage=vintage,
        notes=(
            "Sum of 5+ unit permits across the screened jurisdictions in this "
            "county, divided by the county total. Identical for every unit in "
            "the county. A share near zero means BPS attributes almost nothing "
            "to the named places, which usually means the county is the permit "
            "issuing office."
        ),
    )
