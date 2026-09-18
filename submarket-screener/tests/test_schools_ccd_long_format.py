"""The CCD staff and lunch files are long format, one row per category.

The first live run read the staff file expecting a wide file with a TEACHERS
column, found none, and gave up, so the student to teacher ratio was MISSING
for every district. The lunch file was never requested at all, so FRPL was
MISSING too, which left the school proxy with no component and the location
pillar running on distance alone.

Every fixture row here is copied from tools/probe_acs_summary_file.py output
against nces.ed.gov on 2026-09-18, for LEAID 5508520, Madison Metropolitan.
"""
from __future__ import annotations

import pytest

from screener.cache import FetchError
from screener.sources.schools import parse_lunch_file, parse_staff_file

STAFF_HEADER = (
    "SCHOOL_YEAR,FIPST,STATENAME,ST,LEA_NAME,STATE_AGENCY_NO,UNION,ST_LEAID,"
    "LEAID,STAFF,STAFF_COUNT,TOTAL_INDICATOR,DMS_FLAG\n"
)


def staff_row(staff: str, count: str, indicator: str, leaid: str = "5508520") -> str:
    return (f"2021-2022,55,WISCONSIN,WI,Madison Metropolitan,01,,WI-3269,"
            f"{leaid},{staff},{count},{indicator},Reported\n")


REAL_STAFF = STAFF_HEADER + "".join([
    staff_row("Elementary Teachers", "878.96", "Category Set A"),
    staff_row("Secondary Teachers", "972.80", "Category Set A"),
    staff_row("Paraprofessionals/Instructional Aides", "317.65", "Category Set A"),
    staff_row("Teachers", "2114.93", "Derived - Major Staffing Category"),
    staff_row("School Staff", "947.37", "Derived - Major Staffing Category"),
    staff_row("No Category Codes", "3999.43", "Education Unit Total"),
])


def test_teacher_fte_is_the_derived_teachers_row():
    teachers = parse_staff_file(REAL_STAFF.encode(), label="staff")
    assert teachers == {"5508520": 2114.93}


def test_it_is_not_the_education_unit_total():
    """3999.43 is every employee including aides and administrators. Using it
    would show roughly 1.9 students per teacher where the truth is near 4, and
    nothing about the number would look wrong."""
    teachers = parse_staff_file(REAL_STAFF.encode(), label="staff")
    assert teachers["5508520"] != 3999.43


def test_the_grade_level_rows_are_not_added_to_the_derived_total():
    """The derived 'Teachers' row already sums the grade level rows.

    It is larger than elementary plus secondary alone (2114.93 against 1851.76)
    because it also covers kindergarten, pre-kindergarten and ungraded, so a
    simple size comparison proves nothing. What proves it is that adding
    another grade level row leaves the answer untouched.
    """
    baseline = parse_staff_file(REAL_STAFF.encode(), label="staff")["5508520"]
    with_more = REAL_STAFF + staff_row("Kindergarten Teachers", "109.20", "Category Set A")
    assert parse_staff_file(with_more.encode(), label="staff")["5508520"] == baseline


def test_a_staff_file_with_no_teachers_row_is_an_error():
    only_aides = STAFF_HEADER + staff_row(
        "Paraprofessionals/Instructional Aides", "317.65", "Category Set A")
    with pytest.raises(FetchError) as caught:
        parse_staff_file(only_aides.encode(), label="staff")
    assert "teachers" in str(caught.value).lower()


LUNCH_HEADER = (
    "SCHOOL_YEAR,FIPST,STATENAME,ST,SCH_NAME,STATE_AGENCY_NO,UNION,ST_LEAID,"
    "LEAID,ST_SCHID,NCESSCH,SCHID,DATA_GROUP,LUNCH_PROGRAM,STUDENT_COUNT,"
    "TOTAL_INDICATOR,DMS_FLAG\n"
)


def lunch_row(school: str, group: str, program: str, count: str, indicator: str,
              leaid: str = "5508520") -> str:
    return (f"2021-2022,55,WISCONSIN,WI,{school},01,,WI-3269,{leaid},"
            f"WI-3269-0440,550852000373,5500373,{group},{program},{count},"
            f"{indicator},Reported\n")


REAL_LUNCH = LUNCH_HEADER + "".join([
    lunch_row("James Wright Middle", "Direct Certification", "Not Applicable", "",
              "Education Unit Total"),
    lunch_row("James Wright Middle", "Free and Reduced-price Lunch Table",
              "No Category Codes", "174", "Education Unit Total"),
    lunch_row("James Wright Middle", "Free and Reduced-price Lunch Table",
              "Free lunch qualified", "174", "Category Set A"),
    lunch_row("James Wright Middle", "Free and Reduced-price Lunch Table",
              "Reduced-price lunch qualified", "0", "Category Set A"),
    lunch_row("Spring Harbor Middle", "Free and Reduced-price Lunch Table",
              "No Category Codes", "57", "Education Unit Total"),
    lunch_row("Spring Harbor Middle", "Free and Reduced-price Lunch Table",
              "Free lunch qualified", "53", "Category Set A"),
    lunch_row("Spring Harbor Middle", "Free and Reduced-price Lunch Table",
              "Reduced-price lunch qualified", "4", "Category Set A"),
])


def test_the_district_total_is_the_sum_over_its_schools():
    """CCD publishes FRPL per school only, so the district figure is a sum."""
    assert parse_lunch_file(REAL_LUNCH.encode(), label="lunch") == {"5508520": 231.0}


def test_the_category_rows_are_not_added_on_top_of_the_school_total():
    """174 + 0 + 53 + 4 would double the answer: the Education Unit Total row
    is already free plus reduced for that school."""
    assert parse_lunch_file(REAL_LUNCH.encode(), label="lunch")["5508520"] == 231.0


def test_direct_certification_is_a_different_measure_and_is_excluded():
    """It counts students certified through another benefits programme. Adding
    it to an FRPL count mixes two definitions in one column."""
    with_direct = REAL_LUNCH + lunch_row(
        "Sandburg Elementary", "Direct Certification", "No Category Codes", "999",
        "Education Unit Total")
    assert parse_lunch_file(with_direct.encode(), label="lunch") == {"5508520": 231.0}


def test_schools_across_two_districts_are_kept_apart():
    two = REAL_LUNCH + lunch_row(
        "Other School", "Free and Reduced-price Lunch Table", "No Category Codes",
        "40", "Education Unit Total", leaid="5503180")
    assert parse_lunch_file(two.encode(), label="lunch") == {
        "5508520": 231.0, "5503180": 40.0,
    }


def test_a_lunch_file_with_no_lunch_table_rows_is_an_error():
    only_direct = LUNCH_HEADER + lunch_row(
        "James Wright Middle", "Direct Certification", "Not Applicable", "",
        "Education Unit Total")
    with pytest.raises(FetchError):
        parse_lunch_file(only_direct.encode(), label="lunch")
