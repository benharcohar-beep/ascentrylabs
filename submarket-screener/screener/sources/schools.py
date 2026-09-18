"""School quality PROXY per submarket, built from NCES Common Core of Data.

Read the LIMITATIONS block before you read anything else. This module does not
measure school quality. It measures two things that are cheap and free to get
(student poverty and a staffing ratio) and turns them into a relative ranking
inside one market. Anyone who presents the output as a school quality score is
misrepresenting it.

# LIMITATIONS
#
# 1. This is a PROXY, not a measure of teaching quality, and nothing in the
#    two inputs is a measure of what a child learns.
# 2. Free and reduced price lunch (FRPL) eligibility is a measure of STUDENT
#    POVERTY. It correlates with test scores mostly because it proxies
#    household income. This screen already scores household income directly
#    under the demand pillar, so the school proxy and the demand pillar are not
#    independent evidence. Scoring both and adding them up double counts the
#    same underlying fact about a neighbourhood. Say that out loud in any
#    committee memo that uses this column.
# 3. The student to teacher ratio is a staffing ratio, not a class size, and
#    not a measure of teacher quality. Districts count teacher FTE differently,
#    and special education and specialist staffing move the ratio for reasons
#    that have nothing to do with the classroom a typical child sits in.
# 4. A real underwriting process would buy GreatSchools or Niche data, or pull
#    state assessment results directly from the state education agency, which
#    is the only way to get an outcome measure rather than an input measure.
# 5. NCES EDFacts does publish district level proficiency rates, but they are
#    released in COARSE BINS (for example "GE50", "70-79", "LT50") to protect
#    small cells. Two districts reported as "70-79" cannot be separated, which
#    makes the small differences that actually distinguish neighbouring
#    suburban districts unusable. That is why this module does not use them.
# 6. The composite is a PERCENTILE RANK WITHIN ONE MARKET. It is not
#    comparable across markets and it is not an absolute grade. Running the
#    screen on a different candidate list changes every number in the column.
# 7. One submarket is mapped to ONE district by testing the submarket centroid
#    against school district polygons. Large municipalities are routinely split
#    across several districts, and this method is blind to that. It is also
#    blind to charter, magnet and private enrolment, and to school choice or
#    open enrolment programmes that let families cross district lines.
# 8. Attendance boundaries WITHIN a district are not modelled at all. In a
#    district with a strong school and a weak school the proxy gives the same
#    number to both halves of the district.
# 9. FRPL counts have been distorted since the Community Eligibility Provision
#    (CEP) let high poverty schools serve free meals to every student without
#    collecting household applications. A CEP district can report an FRPL share
#    near 100 percent that is not comparable with a non CEP neighbour.
# 10. District boundaries (TIGER) and district finances and counts (CCD) are
#    different vintages and are only approximately aligned. Districts that
#    consolidated or dissolved between the two vintages will not join.
# 11. Without geopandas installed there is no point in polygon test available,
#    so every school column is returned MISSING. The module never guesses a
#    district from a name or a county.
"""
from __future__ import annotations

import csv
import io
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..cache import FetchError
from ..provenance import MetricSpec, Unit, Value, missing

SOURCE_NAME = "NCES Common Core of Data (district counts) and Census TIGER/Line school district boundaries"


# --------------------------------------------------------------------------
# Metric surface
# --------------------------------------------------------------------------

METRICS: list[MetricSpec] = [
    MetricSpec(
        key="school_proxy_index",
        label="School quality proxy (0 to 100)",
        pillar="location",
        higher_is_better=True,
        unit="index",
        decimals=0,
        scored=True,
        description=(
            "PROXY ONLY. Equal weighted average of two within market percentile "
            "ranks: inverted free and reduced price lunch share, and inverted "
            "student to teacher ratio. Both are input measures, neither is an "
            "outcome measure, and the FRPL half largely restates household "
            "income which the demand pillar already scores."
        ),
    ),
]

# Unscored context columns. `higher_is_better` is carried for completeness but
# is ignored by the scorer because scored=False on all of these.
CONTEXT_COLUMNS: list[MetricSpec] = [
    MetricSpec(
        key="school_district_name",
        label="School district",
        pillar="location",
        higher_is_better=True,
        unit="",
        decimals=0,
        scored=False,
        description="Name of the district whose polygon contains the submarket centroid.",
    ),
    MetricSpec(
        key="school_district_leaid",
        label="District LEAID",
        pillar="location",
        higher_is_better=True,
        unit="",
        decimals=0,
        scored=False,
        description=(
            "7 digit NCES local education agency identifier (state FIPS + 5 digit "
            "LEA code). This is the join key between the TIGER polygon GEOID and "
            "the CCD district files."
        ),
    ),
    MetricSpec(
        key="school_frpl_share",
        label="Free or reduced price lunch share",
        pillar="location",
        higher_is_better=False,
        unit="share",
        decimals=3,
        scored=False,
        description=(
            "Share of district students eligible for free or reduced price lunch. "
            "A STUDENT POVERTY measure, not a school quality measure. Distorted "
            "upward in districts using the Community Eligibility Provision."
        ),
    ),
    MetricSpec(
        key="school_student_teacher_ratio",
        label="Students per teacher",
        pillar="location",
        higher_is_better=False,
        unit="ratio",
        decimals=1,
        scored=False,
        description=(
            "District students divided by teacher FTE. A staffing ratio, not a "
            "class size and not a quality measure."
        ),
    ),
    MetricSpec(
        key="school_proxy_components",
        label="Proxy components used",
        pillar="location",
        higher_is_better=True,
        unit="",
        decimals=0,
        scored=False,
        description=(
            "Which of the two components were available for this submarket: "
            "'frpl+ratio', 'frpl only', 'ratio only' or 'none'. Read this before "
            "you read the index: a 'frpl only' row and a 'frpl+ratio' row are not "
            "built from the same thing."
        ),
    ),
]

_ALL_KEYS = [m.key for m in METRICS] + [c.key for c in CONTEXT_COLUMNS]


# --------------------------------------------------------------------------
# Honesty boilerplate that gets attached to Value.notes
# --------------------------------------------------------------------------

PROXY_CAVEAT = (
    "PROXY ONLY, not a measure of school quality or teaching quality. Built "
    "from free and reduced price lunch eligibility (a STUDENT POVERTY measure) "
    "and the student to teacher ratio (a staffing ratio). FRPL correlates with "
    "test scores mainly because it proxies household income, which this screen "
    "already scores under the demand pillar, so the two columns are not "
    "independent evidence and adding both double counts the same fact. A real "
    "underwriting process would buy GreatSchools or Niche data or pull state "
    "assessment results. NCES EDFacts does publish district level proficiency, "
    "but only in coarse bins (for example 'GE50' or '70-79'), which makes the "
    "small differences between neighbouring districts unusable."
)

CENTROID_CAVEAT = (
    "The district was found by testing the submarket centroid against school "
    "district polygons. A large municipality can be split across several "
    "districts and this method sees only the district containing the centroid. "
    "Attendance boundaries inside a district are not modelled at all."
)

RANK_CAVEAT = (
    "Percentile ranks are computed ACROSS THE CANDIDATE SUBMARKETS IN THIS "
    "MARKET ONLY. The number is a relative position inside one candidate list, "
    "not an absolute grade, and it is not comparable with another market's run."
)

GEOPANDAS_MISSING_REASON = (
    "geopandas not installed; run pip install geopandas to enable the school "
    "district lookup"
)


# --------------------------------------------------------------------------
# Manual drop path. THIS IS THE PATH THAT IS EXPECTED TO WORK.
# --------------------------------------------------------------------------
#
# nces.ed.gov is one of the hosts blocked from the machine this was written on,
# and the CCD flat file names carry a release date suffix that changes with
# every publication, so no URL below could be verified. The reliable route is
# therefore a hand download.
#
# Put the two files here (this resolves to data/cache/manual/ by default,
# because ctx.cache.root is data/cache):
#
#   data/cache/manual/ccd_lea_directory.csv
#   data/cache/manual/ccd_lea_membership.csv
#
# COLUMNS NEEDED FROM ccd_lea_directory.csv
#   LEAID      7 character NCES district id. Accepted header spellings:
#              "LEAID", "NCES District ID", or the ElSi export header
#              "Agency ID - NCES Assigned [District] Latest available year".
#   LEA_NAME   district name. Accepted: "LEA_NAME", "Agency Name",
#              "District Name", "NAME".
#   Optional:  "SCH_YEAR" or "SURVYEAR", used only to fill Value.vintage.
#
# COLUMNS NEEDED FROM ccd_lea_membership.csv
#   LEAID      as above, required.
#   Then whatever of the following the export happens to carry. At least one of
#   the two components has to be derivable or every district comes back MISSING.
#     free/reduced count : "FREE_AND_REDUCED_LUNCH", "FRPL_COUNT",
#                          "Free and Reduced Lunch Students [Public School] ..."
#     OR a ready made share/percent : "FRPL_SHARE", "FRPL_PCT",
#                          "Percent Free and Reduced Lunch ..."
#     total students     : "TOTAL_STUDENTS", "MEMBER", "STUDENT_COUNT",
#                          "Total Students All Grades (Excludes AE) ..."
#     teacher FTE        : "TEACHERS", "FTE_TEACHERS", "TEACHERS_FTE",
#                          "Full-Time Equivalent (FTE) Teachers ..."
#     OR a ready made ratio : "PUPIL_TEACHER_RATIO", "STUDENT_TEACHER_RATIO",
#                          "Pupil/Teacher Ratio [Public School] ..."
#
# The easiest single source for the membership file is the NCES ElSi table
# generator at https://nces.ed.gov/ccd/elsi/ , which exports district level
# FRPL counts, total students and the pupil/teacher ratio in one CSV. ElSi
# appends the school year to every column header, which is why the column
# resolver below matches on a normalised PREFIX as well as on an exact name.

MANUAL_SUBDIR = "manual"
MANUAL_DIRECTORY_FILENAME = "ccd_lea_directory.csv"
MANUAL_MEMBERSHIP_FILENAME = "ccd_lea_membership.csv"


# --------------------------------------------------------------------------
# Download path. Every URL here is UNVERIFIED. See the comment on each list.
# --------------------------------------------------------------------------
#
# The CCD non fiscal flat files live under https://nces.ed.gov/ccd/Data/zip/ and
# are indexed from https://nces.ed.gov/ccd/files.asp . The file name pattern is
#   ccd_<level>_<survey>_<schoolyear>_<w|l>_<version>_<mmddyy>.zip
# where <mmddyy> is the RELEASE date, not the data date. The release date suffix
# is the part that cannot be guessed, so each list below holds several plausible
# spellings and they are tried in order.

CCD_ZIP_BASE = "https://nces.ed.gov/ccd/Data/zip"

# Survey 029: LEA (School District) Universe Survey directory file. Supplies
# LEAID and LEA_NAME. Newest school year first.
CCD_LEA_DIRECTORY_URLS: list[str] = [
    f"{CCD_ZIP_BASE}/ccd_lea_029_2223_w_1a_071823.zip",
    f"{CCD_ZIP_BASE}/ccd_lea_029_2122_w_1a_071722.zip",
    f"{CCD_ZIP_BASE}/ccd_lea_029_2021_w_1a_080621.zip",
    # "LEA Universe Survey Longitudinal Data", one file covering many years.
    # Larger but the name has no release date suffix to guess wrong.
    f"{CCD_ZIP_BASE}/ccd_lea_029_LongitudinalData.zip",
]

# Survey 052: LEA membership (student counts). Long format, one row per
# LEAID x grade x race x sex, plus summary rows flagged by TOTAL_INDICATOR.
CCD_LEA_MEMBERSHIP_URLS: list[str] = [
    f"{CCD_ZIP_BASE}/ccd_lea_052_2223_l_1a_071823.zip",
    f"{CCD_ZIP_BASE}/ccd_lea_052_2122_l_1a_071722.zip",
    f"{CCD_ZIP_BASE}/ccd_lea_052_2021_l_1a_080621.zip",
]

# Survey 059: LEA staff counts. Teacher FTE arrives here, NOT in survey 052,
# which is why the student to teacher ratio needs a third file.
CCD_LEA_STAFF_URLS: list[str] = [
    f"{CCD_ZIP_BASE}/ccd_lea_059_2223_l_1a_071823.zip",
    f"{CCD_ZIP_BASE}/ccd_lea_059_2122_l_1a_071722.zip",
    f"{CCD_ZIP_BASE}/ccd_lea_059_2021_l_1a_080621.zip",
]

# Survey 033: SCHOOL level lunch program eligibility. CCD publishes FRPL at the
# school level only, so the download path has to sum schools up to their LEAID.
# That sum is not identical to a district reported FRPL count: schools with
# suppressed or missing counts drop out of the numerator silently. The manual
# ElSi export is better because ElSi does the aggregation itself.
CCD_SCHOOL_LUNCH_URLS: list[str] = [
    f"{CCD_ZIP_BASE}/ccd_sch_033_2223_l_1a_071823.zip",
    f"{CCD_ZIP_BASE}/ccd_sch_033_2122_l_1a_071722.zip",
    f"{CCD_ZIP_BASE}/ccd_sch_033_2021_l_1a_080621.zip",
]

MANUAL_INSTRUCTIONS = (
    "Could not download the NCES Common Core of Data district files. "
    "Do this by hand, once: go to https://nces.ed.gov/ccd/files.asp , download "
    "the current LEA (School District) Universe Survey DIRECTORY file and the "
    "LEA MEMBERSHIP file (or, easier, build one district level export at "
    "https://nces.ed.gov/ccd/elsi/ containing LEAID, agency name, total "
    "students, free and reduced lunch students and the pupil/teacher ratio), "
    "unzip them, and save them as plain CSV at exactly:\n"
    "    data/cache/manual/ccd_lea_directory.csv\n"
    "    data/cache/manual/ccd_lea_membership.csv\n"
    "The directory file must contain a district id column (LEAID, 'NCES "
    "District ID' or the ElSi 'Agency ID - NCES Assigned [District]' header) "
    "and a district name column (LEA_NAME, 'Agency Name' or 'District Name'). "
    "The membership file must contain the same district id column plus at "
    "least one of: free and reduced lunch students with total students, a "
    "ready made FRPL percentage, teacher FTE with total students, or a ready "
    "made pupil/teacher ratio. When those two files exist the download is "
    "skipped entirely."
)


# --------------------------------------------------------------------------
# TIGER school district boundaries
# --------------------------------------------------------------------------
#
# GEOID on all three layers is state FIPS (2) + local education agency code (5),
# which is exactly the 7 character CCD LEAID. That join is the whole reason this
# module works without any name matching.
#
# UNSD = unified districts (one district covers all grades). Most of the country.
# ELSD = elementary districts, SCSD = secondary districts. Several states
# (Arizona, California, Illinois, New Jersey and others) split grades between an
# elementary district and a high school district, and in those states a point
# falls in NO unified polygon. ELSD and SCSD files DO NOT EXIST for states with
# no such districts, so a 404 on those two is normal and is not an error.

TIGER_YEAR = "2024"
TIGER_UNSD_URL = "https://www2.census.gov/geo/tiger/TIGER{year}/UNSD/tl_{year}_{state}_unsd.zip"
TIGER_ELSD_URL = "https://www2.census.gov/geo/tiger/TIGER{year}/ELSD/tl_{year}_{state}_elsd.zip"
TIGER_SCSD_URL = "https://www2.census.gov/geo/tiger/TIGER{year}/SCSD/tl_{year}_{state}_scsd.zip"

# Tried in this order. First polygon that contains the centroid wins.
TIGER_LAYERS: list[tuple[str, str, str]] = [
    ("UNSD", "unified school district", TIGER_UNSD_URL),
    ("ELSD", "elementary school district", TIGER_ELSD_URL),
    ("SCSD", "secondary school district", TIGER_SCSD_URL),
]


# --------------------------------------------------------------------------
# Small parsing helpers
# --------------------------------------------------------------------------

# ElSi exports use typographic symbols for the various flavours of "no number
# here". They are built with chr() below on purpose, because this repository
# forbids literal en and em dashes in source.
_MISSING_TOKENS = {
    "",
    "-",
    "--",
    chr(0x2013),    # en dash, ElSi "not applicable". Spelled with chr() because
                    # this repository forbids a literal en dash in source.
    chr(0x2014),    # em dash, same reason.
    chr(0x2020),    # dagger, ElSi "not applicable"
    chr(0x2021),    # double dagger, ElSi "reported but not applicable"
    chr(0x00a7),    # section sign, ElSi "missing"
    "n/a",
    "na",
    "nan",
    "none",
    ".",
    "m",
    "s",            # CCD "suppressed"
}


def _norm_header(name: str) -> str:
    """Lower case and strip everything that is not a letter or digit.

    "Free and Reduced Lunch Students [Public School] 2022-23" becomes
    "freeandreducedlunchstudentspublicschool202223", which lets a short
    canonical name match it as a prefix.
    """
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _find_column(
    fieldnames: Sequence[str] | None,
    candidates: Sequence[str],
) -> str | None:
    """Resolve one logical field to an actual header, or None.

    Exact normalised match first, then normalised prefix match (which is what
    catches the school year that ElSi bolts on to the end of every header).
    Nothing fuzzier than that: a substring match anywhere in the header would
    be how a column gets silently mis-parsed, and a silently mis-parsed column
    is the worst possible outcome for this project.
    """
    if not fieldnames:
        return None
    norm_map: dict[str, str] = {}
    for fn in fieldnames:
        norm_map.setdefault(_norm_header(fn), fn)
    for cand in candidates:
        n = _norm_header(cand)
        if n and n in norm_map:
            return norm_map[n]
    for cand in candidates:
        n = _norm_header(cand)
        if not n:
            continue
        for norm, original in norm_map.items():
            if norm.startswith(n):
                return original
    return None


def _to_float(raw: Any) -> float | None:
    """Parse a CCD or ElSi cell to a float, or None. Never returns 0 for blank.

    Zero is a real number in this data (a district really can report zero
    reduced price lunch students) and must never stand in for "not reported".
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if text.lower() in _MISSING_TOKENS:
        return None
    text = text.replace(",", "").replace("$", "").replace("%", "").strip()
    if text in ("", "-"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clean_leaid(raw: Any) -> str:
    """LEAID is a 7 character STRING with a meaningful leading zero.

    Every state below FIPS 10 has districts whose LEAID starts with "0", and
    Excel or a naive int() cast eats it. Anything that arrives as "601470.0"
    from a spreadsheet round trip is repaired here.
    """
    text = str(raw or "").strip().strip('"').replace(" ", "")
    if text.endswith(".0"):
        text = text[:-2]
    if not text or not text.isdigit():
        return ""
    return text.zfill(7)


def _read_csv_rows(data: bytes, *, label: str) -> tuple[list[dict[str, str]], list[str]]:
    """Read a CSV into dict rows. utf-8-sig strips the BOM Excel likes to add."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    if not fieldnames:
        raise FetchError(f"{label}: file has no header row, so no columns could be resolved.")
    rows = [row for row in reader]
    return rows, fieldnames


def _file_retrieved_at(path: Path) -> str:
    """Timestamp for a hand dropped file.

    The contract says retrieved_at must be when the BYTES were obtained, not
    datetime.now(). For a manual drop the honest stand in is the file's
    modification time, which is when the user saved the download.
    """
    stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# District reference data
# --------------------------------------------------------------------------


@dataclass
class DistrictRecord:
    leaid: str
    name: str = ""
    frpl_share: float | None = None            # 0 to 1
    student_teacher_ratio: float | None = None
    frpl_note: str = ""
    ratio_note: str = ""


@dataclass
class DistrictReference:
    records: dict[str, DistrictRecord]
    source: str
    vintage: str
    url: str
    retrieved_at: str
    origin: str                                # "manual drop" or "download"


# Header candidates, most explicit first.
_LEAID_CANDIDATES = (
    "LEAID",
    "NCES District ID",
    "Agency ID - NCES Assigned [District]",
    "Agency ID - NCES Assigned [Public School]",
    "District ID",
)
_NAME_CANDIDATES = (
    "LEA_NAME",
    "Agency Name",
    "District Name",
    "NAME",
)
_YEAR_CANDIDATES = ("SCH_YEAR", "SURVYEAR", "School Year", "SY")

_FRPL_COUNT_CANDIDATES = (
    "FREE_AND_REDUCED_LUNCH",
    "FRPL_COUNT",
    "FRL_COUNT",
    "Free and Reduced Lunch Students",
)
_FRPL_SHARE_CANDIDATES = (
    "FRPL_SHARE",
    "FRPL_PCT",
    "Percent Free and Reduced Lunch",
    "Free and Reduced Lunch Percent",
)
_TOTAL_STUDENTS_CANDIDATES = (
    "TOTAL_STUDENTS",
    "Total Students All Grades (Excludes AE)",
    "Total Students",
    "MEMBER",
    "STUDENT_COUNT",
)
_TEACHER_CANDIDATES = (
    "TEACHERS",
    "TEACHERS_FTE",
    "FTE_TEACHERS",
    "Full-Time Equivalent (FTE) Teachers",
)
_RATIO_CANDIDATES = (
    "PUPIL_TEACHER_RATIO",
    "STUDENT_TEACHER_RATIO",
    "Pupil/Teacher Ratio",
)

# CCD long format files repeat each LEAID across many breakdown rows and flag
# the district wide summary row in TOTAL_INDICATOR. These label strings come
# from the published CCD file documentation and could NOT be verified from this
# machine, so any row whose TOTAL_INDICATOR is not recognised is skipped rather
# than guessed at.
_TOTAL_INDICATOR_CANDIDATES = ("TOTAL_INDICATOR",)
_EDUCATION_UNIT_TOTAL = "education unit total"


def parse_directory_file(
    data: bytes, *, label: str
) -> tuple[dict[str, str], str]:
    """Parse the LEA directory into {leaid: district name} plus a vintage string."""
    rows, fieldnames = _read_csv_rows(data, label=label)
    leaid_col = _find_column(fieldnames, _LEAID_CANDIDATES)
    name_col = _find_column(fieldnames, _NAME_CANDIDATES)
    if leaid_col is None or name_col is None:
        raise FetchError(
            f"{label}: could not find the columns this module needs. "
            f"Expected a district id column (one of {list(_LEAID_CANDIDATES)}) and a "
            f"district name column (one of {list(_NAME_CANDIDATES)}). "
            f"Found headers: {fieldnames[:25]}. "
            "The NCES layout may have changed, or the wrong file was saved."
        )
    year_col = _find_column(fieldnames, _YEAR_CANDIDATES)

    names: dict[str, str] = {}
    vintage = ""
    for row in rows:
        leaid = _clean_leaid(row.get(leaid_col))
        if not leaid:
            continue
        name = (row.get(name_col) or "").strip()
        if name and leaid not in names:
            names[leaid] = name
        if year_col and not vintage:
            candidate = (row.get(year_col) or "").strip()
            if candidate and candidate.lower() not in _MISSING_TOKENS:
                vintage = candidate
    if not names:
        raise FetchError(
            f"{label}: header parsed but no usable district rows were found. "
            f"Expected 7 digit values in column '{leaid_col}'."
        )
    return names, vintage


def parse_membership_file(
    data: bytes, *, label: str
) -> dict[str, DistrictRecord]:
    """Parse the membership / metrics file into per district components.

    Accepts two shapes:
      a) a wide district level export (ElSi style), one row per district, with
         FRPL counts, total students and/or a ready made pupil/teacher ratio.
      b) a raw CCD long format file with a TOTAL_INDICATOR column, in which case
         only the "Education Unit Total" rows are used.
    """
    rows, fieldnames = _read_csv_rows(data, label=label)
    leaid_col = _find_column(fieldnames, _LEAID_CANDIDATES)
    if leaid_col is None:
        raise FetchError(
            f"{label}: no district id column. Expected one of "
            f"{list(_LEAID_CANDIDATES)}. Found headers: {fieldnames[:25]}."
        )

    frpl_count_col = _find_column(fieldnames, _FRPL_COUNT_CANDIDATES)
    frpl_share_col = _find_column(fieldnames, _FRPL_SHARE_CANDIDATES)
    total_col = _find_column(fieldnames, _TOTAL_STUDENTS_CANDIDATES)
    teacher_col = _find_column(fieldnames, _TEACHER_CANDIDATES)
    ratio_col = _find_column(fieldnames, _RATIO_CANDIDATES)
    total_indicator_col = _find_column(fieldnames, _TOTAL_INDICATOR_CANDIDATES)

    if not any([frpl_count_col, frpl_share_col, total_col, teacher_col, ratio_col]):
        # None of the five numeric columns is present. That is a layout problem
        # with the file, not a district that happens not to report, so raise
        # rather than hand back a column of MISSING that looks like real data.
        raise FetchError(
            f"{label}: found the district id column '{leaid_col}' but none of the "
            "numeric columns this module can use. Expected at least one of: "
            f"{list(_FRPL_COUNT_CANDIDATES)}, {list(_FRPL_SHARE_CANDIDATES)}, "
            f"{list(_TOTAL_STUDENTS_CANDIDATES)}, {list(_TEACHER_CANDIDATES)}, "
            f"{list(_RATIO_CANDIDATES)}. Found headers: {fieldnames[:25]}."
        )

    # Pass 1: collect raw numbers per district.
    raw: dict[str, dict[str, float]] = {}
    for row in rows:
        if total_indicator_col:
            indicator = (row.get(total_indicator_col) or "").strip().lower()
            # Skip the grade / race / sex breakdown rows. Anything that is not
            # the recognised district wide total is left alone on purpose.
            if indicator and indicator != _EDUCATION_UNIT_TOTAL:
                continue
        leaid = _clean_leaid(row.get(leaid_col))
        if not leaid:
            continue
        bucket = raw.setdefault(leaid, {})
        for logical, column in (
            ("frpl_count", frpl_count_col),
            ("frpl_share", frpl_share_col),
            ("total", total_col),
            ("teachers", teacher_col),
            ("ratio", ratio_col),
        ):
            if column is None:
                continue
            parsed = _to_float(row.get(column))
            if parsed is not None and logical not in bucket:
                bucket[logical] = parsed

    # Decide once, for the whole column, whether a supplied share is a
    # percentage or a fraction. Deciding per value would flip units halfway
    # down the file, which is exactly the kind of silent error rule 5 is about.
    share_is_percent = False
    if frpl_share_col is not None:
        name_suggests_percent = any(
            token in _norm_header(frpl_share_col) for token in ("percent", "pct")
        )
        observed = [b["frpl_share"] for b in raw.values() if "frpl_share" in b]
        share_is_percent = name_suggests_percent or (
            bool(observed) and max(observed) > 1.5
        )

    out: dict[str, DistrictRecord] = {}
    for leaid, bucket in raw.items():
        rec = DistrictRecord(leaid=leaid)

        # FRPL share. A supplied share wins over a count, because whoever
        # produced it knew which denominator they used.
        if "frpl_share" in bucket:
            share = bucket["frpl_share"] / 100.0 if share_is_percent else bucket["frpl_share"]
            rec.frpl_share = share
            rec.frpl_note = f"FRPL share taken directly from column '{frpl_share_col}'."
        elif "frpl_count" in bucket and bucket.get("total"):
            total = bucket["total"]
            if total > 0:
                rec.frpl_share = bucket["frpl_count"] / total
                rec.frpl_note = (
                    f"FRPL share computed as '{frpl_count_col}' divided by "
                    f"'{total_col}'."
                )

        # Student to teacher ratio. Again a supplied ratio wins.
        if "ratio" in bucket and bucket["ratio"] > 0:
            rec.student_teacher_ratio = bucket["ratio"]
            rec.ratio_note = f"Ratio taken directly from column '{ratio_col}'."
        elif bucket.get("teachers") and bucket.get("total"):
            teachers = bucket["teachers"]
            if teachers > 0:
                rec.student_teacher_ratio = bucket["total"] / teachers
                rec.ratio_note = (
                    f"Ratio computed as '{total_col}' divided by '{teacher_col}' "
                    "(teacher FTE)."
                )

        # Guard against nonsense that would poison a percentile rank. These are
        # dropped to MISSING rather than clipped, because a clipped value is an
        # invented value.
        if rec.frpl_share is not None and not (0.0 <= rec.frpl_share <= 1.0):
            rec.frpl_share = None
            rec.frpl_note = "FRPL share fell outside 0 to 1 and was discarded."
        if rec.student_teacher_ratio is not None and not (1.0 <= rec.student_teacher_ratio <= 100.0):
            rec.student_teacher_ratio = None
            rec.ratio_note = "Student to teacher ratio fell outside 1 to 100 and was discarded."

        out[leaid] = rec

    if not out:
        raise FetchError(
            f"{label}: header parsed but no usable district rows were found. "
            f"Expected 7 digit values in column '{leaid_col}'."
        )
    return out


def manual_dir(ctx: Any) -> Path:
    """data/cache/manual by default, derived from the configured cache root."""
    return Path(ctx.cache.root) / MANUAL_SUBDIR


def load_manual_reference(ctx: Any) -> DistrictReference | None:
    """Use the hand dropped CCD files if both are present. Otherwise None."""
    directory_path = manual_dir(ctx) / MANUAL_DIRECTORY_FILENAME
    membership_path = manual_dir(ctx) / MANUAL_MEMBERSHIP_FILENAME
    if not (directory_path.exists() and membership_path.exists()):
        return None

    ctx.log(f"schools: using hand dropped CCD files in {manual_dir(ctx)}")
    names, vintage = parse_directory_file(
        directory_path.read_bytes(), label=str(directory_path)
    )
    records = parse_membership_file(
        membership_path.read_bytes(), label=str(membership_path)
    )
    for leaid, rec in records.items():
        rec.name = names.get(leaid, "")
    # Districts present in the directory but absent from the membership export
    # still deserve a name, so the workbook can say which district a submarket
    # is in even when both components are missing.
    for leaid, name in names.items():
        if leaid not in records:
            records[leaid] = DistrictRecord(leaid=leaid, name=name)

    # Both files came off disk at whatever time the user saved them. Use the
    # older of the two mtimes so the stamp is never newer than the data.
    retrieved_at = min(
        _file_retrieved_at(directory_path), _file_retrieved_at(membership_path)
    )
    return DistrictReference(
        records=records,
        source="NCES Common Core of Data, hand downloaded LEA files",
        vintage=vintage or "school year not stated in the supplied files",
        url=f"manual drop: {directory_path} and {membership_path}",
        retrieved_at=retrieved_at,
        origin="manual drop",
    )


def _first_csv_member(data: bytes, *, label: str) -> bytes:
    """Pull the single data member out of a CCD zip."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise FetchError(f"{label}: downloaded bytes are not a zip archive ({exc}).") from exc
    members = [
        n for n in archive.namelist()
        if n.lower().endswith((".csv", ".txt")) and not n.startswith("__MACOSX")
    ]
    if not members:
        raise FetchError(
            f"{label}: zip contains no .csv or .txt member. Members: {archive.namelist()[:10]}."
        )
    return archive.read(sorted(members)[0])


def _try_download(ctx: Any, urls: Iterable[str], *, key_prefix: str, label: str):
    """Try each candidate URL in order. Return (bytes, url, retrieved_at) or None.

    None, not an exception, because ELSD and SCSD files legitimately do not
    exist for every state and a caller has to be able to carry on.
    """
    for url in urls:
        key = f"{key_prefix}__{url.rsplit('/', 1)[-1]}"
        try:
            resp = ctx.cache.get(url, key=key, ttl_days=180)
        except FetchError as exc:
            ctx.log(f"schools: {label} candidate failed ({url}): {exc}")
            continue
        return resp.body, resp.url, resp.retrieved_at
    return None


def download_reference(ctx: Any) -> DistrictReference:
    """Last resort: assemble the reference from the published CCD zips.

    Everything about the file names here is unverified. If it does not work the
    user gets told, precisely, how to do it by hand instead.
    """
    directory = _try_download(
        ctx, CCD_LEA_DIRECTORY_URLS, key_prefix="ccd_lea_directory", label="CCD LEA directory"
    )
    if directory is None:
        raise FetchError(MANUAL_INSTRUCTIONS)
    names, vintage = parse_directory_file(
        _first_csv_member(directory[0], label="CCD LEA directory zip"),
        label="CCD LEA directory",
    )

    membership = _try_download(
        ctx, CCD_LEA_MEMBERSHIP_URLS, key_prefix="ccd_lea_membership", label="CCD LEA membership"
    )
    if membership is None:
        raise FetchError(MANUAL_INSTRUCTIONS)
    records = parse_membership_file(
        _first_csv_member(membership[0], label="CCD LEA membership zip"),
        label="CCD LEA membership",
    )

    # Teacher FTE lives in survey 059, not 052, so the ratio needs a third file.
    # If it cannot be had, the ratio component stays MISSING and the composite
    # falls back to FRPL alone, which is recorded in school_proxy_components.
    staff = _try_download(
        ctx, CCD_LEA_STAFF_URLS, key_prefix="ccd_lea_staff", label="CCD LEA staff"
    )
    if staff is not None:
        try:
            staff_records = parse_membership_file(
                _first_csv_member(staff[0], label="CCD LEA staff zip"),
                label="CCD LEA staff",
            )
            for leaid, rec in staff_records.items():
                if rec.student_teacher_ratio is not None and leaid in records:
                    records[leaid].student_teacher_ratio = rec.student_teacher_ratio
                    records[leaid].ratio_note = rec.ratio_note
        except FetchError as exc:
            ctx.log(f"schools: staff file could not be parsed, ratio stays missing ({exc})")
    else:
        ctx.log("schools: no CCD staff file, student to teacher ratio will be missing.")

    for leaid, name in names.items():
        records.setdefault(leaid, DistrictRecord(leaid=leaid))
        records[leaid].name = name

    return DistrictReference(
        records=records,
        source="NCES Common Core of Data, downloaded LEA files",
        vintage=vintage or "school year not stated in the downloaded files",
        url=directory[1],
        retrieved_at=directory[2],
        origin="download",
    )


def load_reference(ctx: Any) -> DistrictReference:
    """Manual drop first, download second. Raises FetchError if neither works."""
    manual = load_manual_reference(ctx)
    if manual is not None:
        return manual
    ctx.log(
        "schools: no hand dropped CCD files found, attempting download. "
        f"To skip this, see {MANUAL_DIRECTORY_FILENAME} and "
        f"{MANUAL_MEMBERSHIP_FILENAME} in {manual_dir(ctx)}"
    )
    return download_reference(ctx)


# --------------------------------------------------------------------------
# Geography: submarket centroid to district
# --------------------------------------------------------------------------


def _import_geopandas():
    """Import geopandas or return None.

    Kept as a function so the caller can degrade to MISSING instead of blowing
    up, and so tests can monkeypatch it without touching sys.modules.
    """
    try:
        import geopandas  # noqa: PLC0415
    except Exception:       # noqa: BLE001  ImportError, or a broken GDAL install
        return None
    return geopandas


@dataclass
class DistrictMatch:
    leaid: str
    polygon_name: str
    layer: str              # UNSD | ELSD | SCSD
    layer_label: str
    url: str
    retrieved_at: str


def _load_layer(ctx: Any, gpd, state_fips: str, layer: str, url_template: str):
    """Download and open one TIGER school district layer for one state."""
    url = url_template.format(year=TIGER_YEAR, state=state_fips)
    key = f"tiger{TIGER_YEAR}_{layer.lower()}_{state_fips}"
    try:
        # TIGER boundaries change once a year at most, so a long TTL is right.
        resp = ctx.cache.get(url, key=key, ttl_days=365)
    except FetchError as exc:
        # Expected for ELSD and SCSD in states with no such districts.
        ctx.log(f"schools: no {layer} layer for state {state_fips} ({exc})")
        return None
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / f"tl_{TIGER_YEAR}_{state_fips}_{layer.lower()}.zip"
        zip_path.write_bytes(resp.body)
        try:
            frame = gpd.read_file(f"zip://{zip_path}")
        except Exception as exc:    # noqa: BLE001  any GDAL/pyogrio failure
            raise FetchError(
                f"could not open the TIGER {layer} shapefile for state {state_fips} "
                f"from {url}: {exc}"
            ) from exc
    if "GEOID" not in frame.columns:
        raise FetchError(
            f"TIGER {layer} shapefile for state {state_fips} has no GEOID column. "
            f"Columns present: {list(frame.columns)[:20]}. Expected GEOID "
            "(state FIPS + 5 digit LEA code) which is the join key to the CCD LEAID."
        )
    return frame, url, resp.retrieved_at


def assign_districts(ctx: Any, gpd, units: Sequence[Unit]) -> dict[str, DistrictMatch]:
    """Point in polygon each submarket centroid against UNSD, then ELSD, then SCSD."""
    from shapely.geometry import Point     # noqa: PLC0415  shapely ships with geopandas

    matches: dict[str, DistrictMatch] = {}
    by_state: dict[str, list[Unit]] = {}
    for unit in units:
        if unit.lat is None or unit.lon is None:
            continue
        by_state.setdefault(unit.state_fips, []).append(unit)

    for state_fips, state_units in sorted(by_state.items()):
        for layer, layer_label, url_template in TIGER_LAYERS:
            remaining = [u for u in state_units if u.geoid not in matches]
            if not remaining:
                break
            loaded = _load_layer(ctx, gpd, state_fips, layer, url_template)
            if loaded is None:
                continue
            frame, url, retrieved_at = loaded
            name_col = "NAME" if "NAME" in frame.columns else None
            for unit in remaining:
                # TIGER is published in NAD83 (EPSG:4269) with coordinates in
                # decimal degrees. Unit centroids are WGS84 lon/lat. The two
                # differ by well under a metre in the lower 48, which cannot
                # move a point across a district line at this scale.
                point = Point(unit.lon, unit.lat)
                hits = frame[frame.contains(point)]
                if len(hits) == 0:
                    continue
                row = hits.iloc[0]
                matches[unit.geoid] = DistrictMatch(
                    leaid=_clean_leaid(row["GEOID"]),
                    polygon_name=str(row[name_col]) if name_col else "",
                    layer=layer,
                    layer_label=layer_label,
                    url=url,
                    retrieved_at=retrieved_at,
                )
    return matches


# --------------------------------------------------------------------------
# The composite
# --------------------------------------------------------------------------


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    """Percentile rank on 0 to 100, computed across the supplied keys only.

    Standard "fraction below plus half the ties" definition. Two consequences
    worth stating because they show up in the workbook:
      - a single unit scores 50, because a rank needs something to rank against;
      - nothing ever scores exactly 0 or 100, which is correct for a relative
        position and is not a bug.
    """
    n = len(values)
    if n == 0:
        return {}
    if n == 1:
        return {next(iter(values)): 50.0}
    observed = list(values.values())
    out: dict[str, float] = {}
    for key, value in values.items():
        below = sum(1 for x in observed if x < value)
        equal = sum(1 for x in observed if x == value)
        out[key] = 100.0 * (below + 0.5 * equal) / n
    return out


def composite_index(
    frpl_by_unit: dict[str, float],
    ratio_by_unit: dict[str, float],
) -> dict[str, tuple[float | None, str]]:
    """Build the 0 to 100 proxy for every unit mentioned in either input.

    Definition, deliberately kept this simple so it can be explained in one
    breath:
      - invert FRPL (a LOWER poverty share ranks higher) and percentile rank it
        across the units in this market;
      - invert the student to teacher ratio (FEWER students per teacher ranks
        higher) and percentile rank it the same way;
      - average the two with equal weight.
    Inversion is done by ranking the negated value, which is identical to
    100 minus the rank of the raw value but keeps the tie handling in one place.
    If only one component is present it is used alone and the caller records
    that in school_proxy_components. If neither is present the result is None
    and the caller returns MISSING. There is no imputation anywhere.

    Returns {unit geoid: (index or None, components label)}.
    """
    frpl_ranks = percentile_ranks({k: -v for k, v in frpl_by_unit.items()})
    ratio_ranks = percentile_ranks({k: -v for k, v in ratio_by_unit.items()})

    out: dict[str, tuple[float | None, str]] = {}
    for geoid in set(frpl_by_unit) | set(ratio_by_unit):
        parts: list[float] = []
        labels: list[str] = []
        if geoid in frpl_ranks:
            parts.append(frpl_ranks[geoid])
            labels.append("frpl")
        if geoid in ratio_ranks:
            parts.append(ratio_ranks[geoid])
            labels.append("ratio")
        if not parts:
            out[geoid] = (None, "none")
            continue
        out[geoid] = (sum(parts) / len(parts), "+".join(labels) if len(labels) > 1 else f"{labels[0]} only")
    return out


# --------------------------------------------------------------------------
# collect()
# --------------------------------------------------------------------------


def _all_missing(reason: str) -> dict[str, Value]:
    return {
        key: missing(reason, source=SOURCE_NAME)
        for key in _ALL_KEYS
    }


def collect(ctx: Any, units: list[Unit]) -> dict[str, dict[str, Value]]:
    """Return {unit.geoid: {metric_key: Value}} for every unit passed in."""
    out: dict[str, dict[str, Value]] = {}

    # Step 0. No geopandas means no point in polygon test. There is no honest
    # fallback here: matching a township name to a district name would join
    # "Byron Township" to "Byron Center Public Schools" wrongly about as often
    # as it joined it rightly, so the whole block goes MISSING instead.
    gpd = _import_geopandas()
    if gpd is None:
        ctx.log(
            "schools: geopandas is NOT importable, so the school district "
            "point in polygon lookup cannot run. Every school column will be "
            "MISSING for every submarket. Install it with: pip install geopandas"
        )
        return {u.geoid: _all_missing(GEOPANDAS_MISSING_REASON) for u in units}

    # Step 1. District reference data. Raises FetchError with hand download
    # instructions if neither the manual drop nor the download works.
    reference = load_reference(ctx)
    ctx.log(
        f"schools: {len(reference.records)} districts loaded from "
        f"{reference.origin} ({reference.vintage})"
    )

    # Step 2. Map each submarket centroid to a district.
    matches = assign_districts(ctx, gpd, units)
    ctx.log(f"schools: matched {len(matches)} of {len(units)} submarkets to a district")

    # Step 3. Gather the two components for the units that have them.
    frpl_by_unit: dict[str, float] = {}
    ratio_by_unit: dict[str, float] = {}
    for unit in units:
        match = matches.get(unit.geoid)
        if match is None:
            continue
        rec = reference.records.get(match.leaid)
        if rec is None:
            continue
        if rec.frpl_share is not None:
            frpl_by_unit[unit.geoid] = rec.frpl_share
        if rec.student_teacher_ratio is not None:
            ratio_by_unit[unit.geoid] = rec.student_teacher_ratio

    # Step 4. Rank and average, across this market's candidate list only.
    composites = composite_index(frpl_by_unit, ratio_by_unit)

    # Step 5. Build the Values.
    for unit in units:
        match = matches.get(unit.geoid)

        if unit.lat is None or unit.lon is None:
            out[unit.geoid] = _all_missing(
                "submarket has no centroid lat/lon, so no district could be identified"
            )
            continue

        if match is None:
            out[unit.geoid] = _all_missing(
                f"centroid ({unit.lat}, {unit.lon}) fell inside no TIGER {TIGER_YEAR} "
                "unified, elementary or secondary school district polygon"
            )
            continue

        rec = reference.records.get(match.leaid)
        geo_note = (
            f"District matched from the TIGER {TIGER_YEAR} {match.layer_label} "
            f"layer ({match.layer}). {CENTROID_CAVEAT}"
        )
        if match.layer in ("ELSD", "SCSD"):
            geo_note += (
                " This state splits grades between elementary and secondary "
                "districts, so this row describes only one of the two districts "
                "a child here would attend."
            )

        cells: dict[str, Value] = {}

        # District identity comes from the TIGER polygon, so it is sourced and
        # stamped from the shapefile download, not from the CCD files.
        cells["school_district_leaid"] = Value(
            match.leaid,
            source=f"Census TIGER/Line {TIGER_YEAR} {match.layer}",
            vintage=f"TIGER/Line {TIGER_YEAR}",
            url=match.url,
            retrieved_at=match.retrieved_at,
            notes=geo_note,
        )

        district_name = ""
        if rec is not None and rec.name:
            district_name = rec.name
        elif match.polygon_name:
            district_name = match.polygon_name
        if district_name:
            cells["school_district_name"] = Value(
                district_name,
                source=(
                    reference.source if (rec is not None and rec.name)
                    else f"Census TIGER/Line {TIGER_YEAR} {match.layer}"
                ),
                vintage=(
                    reference.vintage if (rec is not None and rec.name)
                    else f"TIGER/Line {TIGER_YEAR}"
                ),
                url=(reference.url if (rec is not None and rec.name) else match.url),
                retrieved_at=(
                    reference.retrieved_at if (rec is not None and rec.name)
                    else match.retrieved_at
                ),
                notes=geo_note,
            )
        else:
            cells["school_district_name"] = missing(
                f"LEAID {match.leaid} is in the TIGER polygons but not in the CCD "
                "district files. Districts that consolidated or dissolved between "
                "the boundary vintage and the CCD vintage do not join.",
                source=SOURCE_NAME,
                url=match.url,
            )

        # FRPL share.
        if rec is not None and rec.frpl_share is not None:
            cells["school_frpl_share"] = Value(
                rec.frpl_share,
                source=reference.source,
                vintage=reference.vintage,
                url=reference.url,
                retrieved_at=reference.retrieved_at,
                notes=(
                    "STUDENT POVERTY measure, not a school quality measure. "
                    + rec.frpl_note
                    + " Districts operating under the Community Eligibility "
                    "Provision serve free meals to all students without "
                    "collecting household applications, which pushes their "
                    "reported share toward 100 percent and breaks comparability "
                    "with non CEP neighbours."
                ),
            )
        else:
            cells["school_frpl_share"] = missing(
                f"no free or reduced price lunch figure for LEAID {match.leaid} in "
                f"the CCD files loaded from {reference.origin}",
                source=reference.source,
                vintage=reference.vintage,
                url=reference.url,
            )

        # Student to teacher ratio.
        if rec is not None and rec.student_teacher_ratio is not None:
            cells["school_student_teacher_ratio"] = Value(
                rec.student_teacher_ratio,
                source=reference.source,
                vintage=reference.vintage,
                url=reference.url,
                retrieved_at=reference.retrieved_at,
                notes=(
                    "Staffing ratio, not a class size and not a teaching quality "
                    "measure. " + rec.ratio_note
                    + " Districts count teacher FTE differently, and special "
                    "education and specialist staffing move this number for "
                    "reasons unrelated to a typical classroom."
                ),
            )
        else:
            cells["school_student_teacher_ratio"] = missing(
                f"no teacher FTE or pupil/teacher ratio for LEAID {match.leaid} in "
                f"the CCD files loaded from {reference.origin}",
                source=reference.source,
                vintage=reference.vintage,
                url=reference.url,
            )

        index_value, components = composites.get(unit.geoid, (None, "none"))

        cells["school_proxy_components"] = Value(
            components,
            source=SOURCE_NAME,
            vintage=reference.vintage,
            url=reference.url,
            retrieved_at=reference.retrieved_at,
            notes=(
                "'frpl+ratio' means both components were available, 'frpl only' "
                "or 'ratio only' means the index rests on a single input, 'none' "
                "means the index is MISSING. Rows built from different components "
                "are not comparable with each other."
            ),
        )

        if index_value is None:
            cells["school_proxy_index"] = missing(
                f"neither a free or reduced price lunch share nor a student to "
                f"teacher ratio was available for LEAID {match.leaid}, so no proxy "
                "could be formed",
                source=SOURCE_NAME,
                vintage=reference.vintage,
                url=reference.url,
            )
        else:
            cells["school_proxy_index"] = Value(
                index_value,
                source=SOURCE_NAME,
                vintage=reference.vintage,
                url=reference.url,
                retrieved_at=reference.retrieved_at,
                notes=(
                    f"Components used: {components}. "
                    + RANK_CAVEAT
                    + " "
                    + PROXY_CAVEAT
                    + " "
                    + geo_note
                ),
            )

        out[unit.geoid] = cells

    # Contract rule 4: every unit passed in comes back, no exceptions.
    for unit in units:
        out.setdefault(
            unit.geoid,
            _all_missing("unit was not processed by the schools module"),
        )
    return out
