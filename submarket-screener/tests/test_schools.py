"""Offline tests for screener/sources/schools.py.

Nothing here touches the network. The TIGER download and the point in polygon
test are never exercised: what is exercised is the CCD parsing, the composite
maths, and the promise that a machine without geopandas gets MISSING cells
rather than an exception. These tests pass whether or not geopandas is
installed, because the one test that cares monkeypatches the import helper.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from screener.cache import FetchError                       # noqa: E402
from screener.provenance import Unit                        # noqa: E402
from screener.sources import schools                        # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CCD_DIRECTORY = FIXTURES / "ccd_lea_directory_SYNTHETIC_v1.csv"
CCD_MEMBERSHIP = FIXTURES / "ccd_lea_membership_SYNTHETIC_v1.csv"
ELSI_EXPORT = FIXTURES / "elsi_lea_export_SYNTHETIC_v1.csv"


# ---------------------------------------------------------------- stub context


class _StubCache:
    """Stands in for screener.cache.Cache. Any network call is a test failure."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def get(self, *args, **kwargs):      # pragma: no cover  must never run
        raise AssertionError("tests must not hit the network")


class StubContext:
    def __init__(self, root: Path) -> None:
        self.cache = _StubCache(root)
        self.messages: list[str] = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


def _ctx_with_manual_files(tmp_path: Path, directory: Path, membership: Path) -> StubContext:
    cache_root = tmp_path / "cache"
    manual = cache_root / schools.MANUAL_SUBDIR
    manual.mkdir(parents=True)
    shutil.copy(directory, manual / schools.MANUAL_DIRECTORY_FILENAME)
    shutil.copy(membership, manual / schools.MANUAL_MEMBERSHIP_FILENAME)
    return StubContext(cache_root)


def _unit(geoid: str, *, lat: float = 42.9, lon: float = -85.6) -> Unit:
    return Unit(
        geoid=geoid,
        name=f"SYNTHETIC unit {geoid}",
        geo_type="county_subdivision",
        state_fips="26",
        county_fips="26081",
        county_name="Kent County",
        lat=lat,
        lon=lon,
    )


# ---------------------------------------------------------------- module shape


def test_module_surface_matches_the_contract():
    assert isinstance(schools.SOURCE_NAME, str) and schools.SOURCE_NAME
    assert [m.key for m in schools.METRICS] == ["school_proxy_index"]
    assert [c.key for c in schools.CONTEXT_COLUMNS] == [
        "school_district_name",
        "school_district_leaid",
        "school_frpl_share",
        "school_student_teacher_ratio",
        "school_proxy_components",
    ]
    index = schools.METRICS[0]
    assert index.pillar == "location"
    assert index.higher_is_better is True
    assert index.unit == "index"
    assert index.scored is True
    for spec in schools.CONTEXT_COLUMNS:
        assert spec.scored is False
        assert spec.pillar == "location"


def test_no_dashes_anywhere_in_the_module_source():
    """House rule: no em dashes or en dashes, including in comments.

    The module does need the en dash as a DATA value, because ElSi writes one
    into cells meaning "not applicable". It builds that character with chr()
    rather than typing it, and this test is what keeps that honest. The two
    characters are spelled with chr() here for the same reason.
    """
    text = Path(schools.__file__).read_text(encoding="utf-8")
    assert chr(0x2014) not in text, "em dash found in screener/sources/schools.py"
    assert chr(0x2013) not in text, "en dash found in screener/sources/schools.py"


# ---------------------------------------------------------------- CCD parsing


def test_parse_directory_file_from_manual_drop_csv():
    names, vintage = schools.parse_directory_file(
        CCD_DIRECTORY.read_bytes(), label="directory fixture"
    )
    assert names["2600001"] == "SYNTHETIC Alpha Public Schools"
    assert names["2600009"] == "SYNTHETIC Zeta Directory Only Schools"
    assert len(names) == 6
    assert vintage == "2022-2023"


def test_parse_membership_file_derives_share_and_ratio_from_counts():
    records = schools.parse_membership_file(
        CCD_MEMBERSHIP.read_bytes(), label="membership fixture"
    )
    assert records["2600001"].frpl_share == pytest.approx(0.10)
    assert records["2600001"].student_teacher_ratio == pytest.approx(20.0)
    assert records["2600002"].frpl_share == pytest.approx(0.20)
    assert records["2600002"].student_teacher_ratio == pytest.approx(16.0)
    assert records["2600004"].frpl_share == pytest.approx(0.40)
    assert records["2600004"].student_teacher_ratio == pytest.approx(25.0)
    # Blank cells are MISSING, never zero. A district that reports nothing must
    # not be confused with a district that reports zero.
    assert records["2600005"].frpl_share is None
    assert records["2600005"].student_teacher_ratio is None


def test_parse_membership_file_reads_an_elsi_export_with_year_suffixed_headers():
    records = schools.parse_membership_file(
        ELSI_EXPORT.read_bytes(), label="ElSi fixture"
    )
    # A "Percent ..." column is divided by 100 for the whole column at once.
    assert records["2600001"].frpl_share == pytest.approx(0.25)
    assert records["2600001"].student_teacher_ratio == pytest.approx(17.5)
    # The dagger is an ElSi "not applicable" marker, so this is MISSING.
    assert records["2600002"].frpl_share is None
    assert records["2600002"].student_teacher_ratio == pytest.approx(18.5)
    # A 6 character id keeps its leading zero.
    assert "0600003" in records
    assert records["0600003"].frpl_share == pytest.approx(0.60)
    assert records["0600003"].student_teacher_ratio is None


def test_parse_directory_file_raises_on_a_layout_change(tmp_path):
    broken = b"SOME_OTHER_ID,SOME_OTHER_NAME\n123,foo\n"
    with pytest.raises(FetchError) as exc:
        schools.parse_directory_file(broken, label="broken directory")
    assert "broken directory" in str(exc.value)
    assert "LEAID" in str(exc.value)


def test_parse_membership_file_raises_when_no_usable_numeric_column():
    broken = b"LEAID,SOMETHING_ELSE\n2600001,7\n"
    with pytest.raises(FetchError) as exc:
        schools.parse_membership_file(broken, label="broken membership")
    assert "broken membership" in str(exc.value)
    assert "PUPIL_TEACHER_RATIO" in str(exc.value)


def test_long_format_membership_uses_only_the_education_unit_total_rows():
    long_format = (
        b"LEAID,TOTAL_INDICATOR,TOTAL_STUDENTS,FREE_AND_REDUCED_LUNCH,TEACHERS\n"
        b"2600001,Category Set A,10,1,1\n"
        b"2600001,Education Unit Total,1000,250,50\n"
        b"2600001,Derived - Education Unit Total minus Adult Education Count,999,9,9\n"
    )
    records = schools.parse_membership_file(long_format, label="long format")
    assert records["2600001"].frpl_share == pytest.approx(0.25)
    assert records["2600001"].student_teacher_ratio == pytest.approx(20.0)


# ------------------------------------------------------------- manual loading


def test_load_manual_reference_uses_the_hand_dropped_files(tmp_path):
    ctx = _ctx_with_manual_files(tmp_path, CCD_DIRECTORY, CCD_MEMBERSHIP)
    ref = schools.load_manual_reference(ctx)
    assert ref is not None
    assert ref.origin == "manual drop"
    assert ref.vintage == "2022-2023"
    assert ref.records["2600001"].name == "SYNTHETIC Alpha Public Schools"
    # Directory only districts survive so the workbook can still name them.
    assert ref.records["2600009"].name == "SYNTHETIC Zeta Directory Only Schools"
    assert ref.records["2600009"].frpl_share is None
    # retrieved_at is the file mtime, not datetime.now().
    assert ref.retrieved_at.endswith("Z") and len(ref.retrieved_at) == 20


def test_load_manual_reference_returns_none_when_files_are_absent(tmp_path):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    assert schools.load_manual_reference(StubContext(cache_root)) is None


def test_load_reference_falls_through_to_download_and_that_failure_is_instructive(tmp_path):
    """With no manual files and no network, the error must tell the user what to do."""
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    ctx = StubContext(cache_root)

    class _DeadCache(_StubCache):
        def get(self, url, **kwargs):
            raise FetchError(f"HTTP 403 from {url}")

    ctx.cache = _DeadCache(cache_root)
    with pytest.raises(FetchError) as exc:
        schools.load_reference(ctx)
    message = str(exc.value)
    assert "https://nces.ed.gov/ccd/files.asp" in message
    assert "data/cache/manual/ccd_lea_directory.csv" in message
    assert "data/cache/manual/ccd_lea_membership.csv" in message


# ------------------------------------------------------------ composite maths


def test_percentile_ranks_basics():
    ranks = schools.percentile_ranks({"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0})
    assert ranks == {"a": 12.5, "b": 37.5, "c": 62.5, "d": 87.5}
    # Two tied values occupy the whole range, so both land at the midpoint.
    tied = schools.percentile_ranks({"a": 1.0, "b": 1.0})
    assert tied == {"a": 50.0, "b": 50.0}
    # A single unit has nothing to rank against.
    # A single unit has nothing to rank against, so it gets no rank at all.
    # Returning 50 here would be inventing a figure.
    assert schools.percentile_ranks({"a": 9.0}) == {}
    assert schools.percentile_ranks({}) == {}


def test_composite_with_both_components():
    frpl = {"a": 0.10, "b": 0.20, "c": 0.30, "d": 0.40}
    ratio = {"a": 17.0, "b": 18.0, "c": 22.0, "d": 25.0}
    result = schools.composite_index(frpl, ratio)
    # Both components agree on the ordering here, so the average equals each rank.
    assert result["a"] == (pytest.approx(87.5), "frpl+ratio")
    assert result["b"] == (pytest.approx(62.5), "frpl+ratio")
    assert result["c"] == (pytest.approx(37.5), "frpl+ratio")
    assert result["d"] == (pytest.approx(12.5), "frpl+ratio")


def test_composite_with_perfectly_opposed_components_flattens_to_fifty():
    """Worth asserting: the two inputs can cancel, and that is not a bug."""
    frpl = {"a": 0.10, "b": 0.20, "c": 0.30, "d": 0.40}
    ratio = {"a": 25.0, "b": 22.0, "c": 18.0, "d": 17.0}
    result = schools.composite_index(frpl, ratio)
    for geoid in "abcd":
        assert result[geoid][0] == pytest.approx(50.0)


def test_composite_with_only_one_component():
    frpl_only = schools.composite_index({"a": 0.10, "b": 0.50}, {})
    assert frpl_only["a"] == (pytest.approx(75.0), "frpl only")
    assert frpl_only["b"] == (pytest.approx(25.0), "frpl only")

    ratio_only = schools.composite_index({}, {"a": 15.0, "b": 30.0})
    assert ratio_only["a"] == (pytest.approx(75.0), "ratio only")
    assert ratio_only["b"] == (pytest.approx(25.0), "ratio only")


def test_composite_with_neither_component():
    assert schools.composite_index({}, {}) == {}


def test_composite_uses_only_components_every_unit_shares():
    """Partial cover on one component drops that component for the whole column.

    An average of two percentile ranks regresses toward 50, while a single rank
    can sit at 5 or 95. Mixing the two shapes in one scored column and then
    ranking them against each other compares different things, so the composite
    uses only the components present for every unit that has any school data.
    Here the ratio covers two units of three, so the whole column falls back to
    FRPL alone rather than scoring 'a' on a different basis from 'c'.
    """
    frpl = {"a": 0.10, "b": 0.20, "c": 0.30}
    ratio = {"a": 16.0, "b": 20.0}
    result = schools.composite_index(frpl, ratio)
    assert result["a"] == (pytest.approx(83.33333333), "frpl only")
    assert result["b"] == (pytest.approx(50.0), "frpl only")
    assert result["c"] == (pytest.approx(16.66666667), "frpl only")


def test_composite_refuses_to_score_when_no_component_covers_everyone():
    """Neither component covers the full set, so nothing shared exists to rank."""
    frpl = {"a": 0.10, "b": 0.20}
    ratio = {"c": 16.0, "d": 20.0}
    result = schools.composite_index(frpl, ratio)
    for geoid in ("a", "b", "c", "d"):
        index, label = result[geoid]
        assert index is None
        assert "not scored" in label


# --------------------------------------------------- geopandas absent degrades


def test_collect_returns_missing_when_geopandas_is_absent(monkeypatch, tmp_path):
    """The whole block goes MISSING. It must not raise, and must not fetch."""
    monkeypatch.setattr(schools, "_import_geopandas", lambda: None)

    # Manual files are present, so any failure here would have to come from the
    # geopandas branch rather than from the CCD loader.
    ctx = _ctx_with_manual_files(tmp_path, CCD_DIRECTORY, CCD_MEMBERSHIP)
    units = [_unit("2608134420"), _unit("2608100000", lat=None, lon=None)]

    result = schools.collect(ctx, units)

    assert set(result) == {u.geoid for u in units}
    expected_keys = {m.key for m in schools.METRICS} | {
        c.key for c in schools.CONTEXT_COLUMNS
    }
    for geoid, cells in result.items():
        assert set(cells) == expected_keys
        for key, value in cells.items():
            assert value.is_missing, f"{geoid}.{key} should be missing"
            assert value.missing_reason == schools.GEOPANDAS_MISSING_REASON
    assert any("geopandas" in m for m in ctx.messages)


def test_collect_with_geopandas_absent_never_reads_the_ccd_files(monkeypatch, tmp_path):
    """Short circuit before any IO: there is nothing useful to do without polygons."""
    monkeypatch.setattr(schools, "_import_geopandas", lambda: None)

    def _explode(_ctx):
        raise AssertionError("load_reference must not be called without geopandas")

    monkeypatch.setattr(schools, "load_reference", _explode)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    result = schools.collect(StubContext(cache_root), [_unit("2608134420")])
    assert result["2608134420"]["school_proxy_index"].is_missing


def test_import_geopandas_helper_is_honest_about_what_it_found():
    """Either a module or None, never a raised ImportError."""
    found = schools._import_geopandas()
    assert found is None or hasattr(found, "read_file")


# ------------------------------------------------------------------- honesty


def test_the_proxy_caveat_names_the_things_it_has_to_name():
    caveat = schools.PROXY_CAVEAT
    for phrase in ("POVERTY", "household income", "demand pillar", "GreatSchools",
                   "Niche", "EDFacts", "bins"):
        assert phrase in caveat, f"PROXY_CAVEAT must mention {phrase}"
    assert "split across several" in schools.CENTROID_CAVEAT


def test_limitations_block_is_present_for_the_readme():
    text = Path(schools.__file__).read_text(encoding="utf-8")
    assert "# LIMITATIONS" in text
