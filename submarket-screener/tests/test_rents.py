"""Offline tests for screener/sources/rents.py.

Every byte these tests parse comes from tests/fixtures/*_SYNTHETIC_*. Nothing
here touches the network: the fake cache below is the only thing collect() can
reach, and it raises if asked for a URL the test did not plan for.

The synthetic ZORI series are deliberately arithmetic (1000 + 10*i and so on)
so the expected weighted numbers can be written out by hand in the assertions
rather than being recomputed by the same code under test.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from screener.cache import CachedResponse, FetchError, MissingCredential
from screener.config import MarketConfig, Weights
from screener.context import Context
from screener.provenance import Unit
from screener.sources import rents

FIXTURES = Path(__file__).parent / "fixtures"

ZORI_CSV = FIXTURES / "zori_zip_SYNTHETIC_3zips_40months.csv"
ZORI_SHORT_CSV = FIXTURES / "zori_zip_SYNTHETIC_too_few_months.csv"
FMR_DICT = FIXTURES / "hud_fmr_SYNTHETIC_county_dict.json"
FMR_LIST_COUNTYWIDE = FIXTURES / "hud_fmr_SYNTHETIC_safmr_list_with_countywide.json"
FMR_LIST_NO_COUNTYWIDE = FIXTURES / "hud_fmr_SYNTHETIC_safmr_list_no_countywide.json"

RETRIEVED_AT = "2026-09-01T00:00:00Z"


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------
class FakeCache:
    """Stands in for screener.cache.Cache. Serves fixtures, never the network."""

    def __init__(self, zori: Path | None = ZORI_CSV, fmr: Path | None = FMR_DICT,
                 zori_error: str | None = None) -> None:
        self.zori = zori
        self.fmr = fmr
        self.zori_error = zori_error
        self.calls: list[dict] = []

    def get(self, url, *, key, params=None, headers=None, method="GET",
            json_body=None, ttl_days=30, expect_content_type=None):
        self.calls.append({"url": url, "key": key, "params": params,
                           "headers": headers})
        if "zillowstatic.com" in url:
            if self.zori_error is not None:
                raise FetchError(self.zori_error)
            assert self.zori is not None
            return CachedResponse(self.zori.read_bytes(), RETRIEVED_AT, url, True)
        if "huduser.gov" in url:
            if self.fmr is None:
                raise FetchError(f"HTTP 404 from {url}")
            return CachedResponse(self.fmr.read_bytes(), RETRIEVED_AT, url, True)
        raise AssertionError(f"test tried to fetch an unplanned URL: {url}")


def make_ctx(cache: FakeCache) -> Context:
    market = MarketConfig(
        key="synthetic",
        name="Synthetic Market",
        short_name="Synthetic",
        states=["26"],
        counties=[{"fips": "26081", "name": "Kent County", "state": "26"}],
        geo_type="county_subdivision",
        geo_type_reason="synthetic fixture",
        employment_centers=[],
    )
    weights = Weights(pillars={"rent": 1.0}, metrics={})
    return Context(cache=cache, market=market, weights=weights,
                   output_dir=Path("."), verbose=False)


# Unit A: two covered ZIPs at 0.7 / 0.3. The aggregation case.
UNIT_A = Unit(
    geoid="2608130000", name="Synthetic Township", geo_type="county_subdivision",
    state_fips="26", county_fips="26081", county_name="Kent County",
    zctas=[("49503", 0.7), ("49546", 0.3)],
)
# Unit B: only 20% of its area is in a ZIP Zillow publishes. The coverage case.
UNIT_B = Unit(
    geoid="2608130001", name="Thin Coverage Township", geo_type="county_subdivision",
    state_fips="26", county_fips="26081", county_name="Kent County",
    zctas=[("49503", 0.2), ("99999", 0.8)],
)
# Unit C: a leading-zero ZCTA whose series stops one month before the file does.
UNIT_C = Unit(
    geoid="2508130002", name="Leading Zero Town", geo_type="county_subdivision",
    state_fips="25", county_fips="25015", county_name="Hampshire County",
    zctas=[("01234", 1.0)],
)
# Unit D: no ZCTA crosswalk at all.
UNIT_D = Unit(
    geoid="2608130003", name="No Crosswalk Township", geo_type="county_subdivision",
    state_fips="26", county_fips="26081", county_name="Kent County",
    zctas=[],
)

ALL_UNITS = [UNIT_A, UNIT_B, UNIT_C, UNIT_D]


@pytest.fixture(autouse=True)
def hud_key(monkeypatch):
    monkeypatch.setenv("HUD_API_KEY", "SYNTHETIC-TEST-TOKEN")


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def test_parses_40_month_columns_without_hardcoding_leading_columns():
    months, series = rents.parse_zori_csv(ZORI_CSV.read_text())
    assert len(months) == 40
    assert months[0] == date(2023, 1, 31)
    assert months[-1] == date(2026, 4, 30)
    assert months == sorted(months)
    # Identifier columns must not be mistaken for months.
    assert set(series) == {"49503", "49546", "01234"}


def test_leading_zero_zip_is_preserved_as_five_characters():
    _, series = rents.parse_zori_csv(ZORI_CSV.read_text())
    assert "01234" in series
    assert "1234" not in series
    # The blank final cell is a gap, not a zero rent.
    assert date(2026, 4, 30) not in series["01234"]
    assert series["01234"][date(2026, 3, 31)] == pytest.approx(690.0)


def test_wanted_filter_keeps_only_the_zips_asked_for():
    _, series = rents.parse_zori_csv(ZORI_CSV.read_text(), wanted={"49546"})
    assert set(series) == {"49546"}


def test_too_few_month_columns_raises_fetcherror_naming_the_zillow_page():
    with pytest.raises(FetchError) as excinfo:
        rents.parse_zori_csv(ZORI_SHORT_CSV.read_text())
    message = str(excinfo.value)
    assert "5" in message
    assert str(rents.MIN_MONTH_COLUMNS) in message
    assert rents.ZORI_ZIP_FILE in message
    assert "https://www.zillow.com/research/data/" in message


def test_missing_regionname_column_raises_fetcherror():
    text = ZORI_CSV.read_text().replace("RegionName", "RegionLabel", 1)
    with pytest.raises(FetchError) as excinfo:
        rents.parse_zori_csv(text)
    assert "RegionName" in str(excinfo.value)


def test_download_failure_message_tells_the_reader_the_file_may_be_renamed():
    ctx = make_ctx(FakeCache(zori_error="HTTP 404 from files.zillowstatic.com"))
    with pytest.raises(FetchError) as excinfo:
        rents.collect(ctx, [UNIT_A])
    message = str(excinfo.value)
    assert rents.ZORI_ZIP_FILE in message
    assert "https://www.zillow.com/research/data/" in message


# --------------------------------------------------------------------------
# Weighted aggregation
# --------------------------------------------------------------------------
def test_weighted_aggregation_across_two_zips_at_70_30():
    ctx = make_ctx(FakeCache())
    out = rents.collect(ctx, [UNIT_A])
    values = out["2608130000"]

    # 2026-04: 49503 = 1390.00, 49546 = 2780.00
    # 0.7 * 1390 + 0.3 * 2780 = 1807.0
    assert values["zori_latest"].value == pytest.approx(1807.0)
    assert values["zori_month"].value == "2026-04"
    assert values["zori_zip_coverage"].value == pytest.approx(1.0)
    assert values["zori_zips_used"].value == "49503,49546"

    # 2025-04: 49503 = 1270.00, 49546 = 2540.00 -> 1651.0
    expected_yoy = (1807.0 / 1651.0 - 1.0) * 100.0
    assert values["zori_yoy"].value == pytest.approx(expected_yoy, abs=1e-3)

    # 2023-04: 49503 = 1030.00, 49546 = 2060.00 -> 1339.0
    expected_cagr = ((1807.0 / 1339.0) ** (1.0 / 3.0) - 1.0) * 100.0
    assert values["zori_cagr_3y"].value == pytest.approx(expected_cagr, abs=1e-3)


def test_growth_uses_the_weighted_series_not_an_average_of_zip_growth_rates():
    """These are two different numbers and the contract asks for the first.

    Weighted levels: 0.7 * 1000 + 0.3 * 2000 = 1300 then 0.7 * 1100 + 0.3 * 2100
    = 1400, so growth on the weighted series is 7.6923%. Averaging the per-ZIP
    growth rates instead gives 0.7 * 10% + 0.3 * 5% = 8.5%. The gap is the
    whole reason the contract specifies which one to build.
    """
    start_month, end_month = date(2025, 4, 30), date(2026, 4, 30)
    series = {
        "A": {start_month: 1000.0, end_month: 1100.0},
        "B": {start_month: 2000.0, end_month: 2100.0},
    }
    weights = [("A", 0.7), ("B", 0.3)]

    start_value, end_value, basket_weight, basket = rents._weighted_window(
        series, weights, start_month, end_month
    )
    assert start_value == pytest.approx(1300.0)
    assert end_value == pytest.approx(1400.0)
    assert basket_weight == pytest.approx(1.0)
    assert sorted(basket) == ["A", "B"]

    weighted_series_growth = (end_value / start_value - 1.0) * 100.0
    average_of_zip_growth = 0.7 * 10.0 + 0.3 * 5.0
    assert weighted_series_growth == pytest.approx(7.6923, abs=1e-3)
    assert weighted_series_growth != pytest.approx(average_of_zip_growth, abs=0.5)


def test_growth_window_drops_zips_missing_at_either_end_and_renormalises():
    start_month, end_month = date(2025, 4, 30), date(2026, 4, 30)
    series = {
        "A": {start_month: 1000.0, end_month: 1100.0},
        # B only starts publishing partway through, so it cannot contribute.
        "B": {end_month: 2100.0},
    }
    weights = [("A", 0.7), ("B", 0.3)]
    start_value, end_value, basket_weight, basket = rents._weighted_window(
        series, weights, start_month, end_month
    )
    assert basket == ["A"]
    # Weights are renormalised inside the window, so A alone carries it.
    assert basket_weight == pytest.approx(0.7)
    assert start_value == pytest.approx(1000.0)
    assert end_value == pytest.approx(1100.0)


def test_latest_month_falls_back_to_the_last_month_this_unit_actually_has():
    ctx = make_ctx(FakeCache())
    values = rents.collect(ctx, [UNIT_C])["2508130002"]
    # 01234 is blank in 2026-04, so the unit's latest month is 2026-03.
    assert values["zori_month"].value == "2026-03"
    assert values["zori_latest"].value == pytest.approx(690.0)
    assert values["zori_zips_used"].value == "01234"


# --------------------------------------------------------------------------
# Coverage threshold
# --------------------------------------------------------------------------
def test_coverage_below_threshold_returns_missing_not_a_number():
    ctx = make_ctx(FakeCache())
    values = rents.collect(ctx, [UNIT_B])["2608130001"]

    assert rents.MIN_ZIP_COVERAGE == 0.25
    assert values["zori_zip_coverage"].value == pytest.approx(0.2)
    for key in ("zori_latest", "zori_yoy", "zori_cagr_3y"):
        assert values[key].is_missing
        assert values[key].missing_reason == (
            "ZORI covers only 20% of this submarket by area; too thin to use"
        )
    # The context columns still explain why, so the gap is readable.
    assert values["zori_month"].value == "2026-04"
    assert values["zori_zips_used"].value == "49503"


def test_unit_with_no_crosswalk_is_missing_with_a_specific_reason():
    ctx = make_ctx(FakeCache())
    values = rents.collect(ctx, [UNIT_D])["2608130003"]
    assert values["zori_latest"].is_missing
    assert "crosswalk" in values["zori_latest"].missing_reason


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------
def test_every_zori_value_carries_provenance_and_the_zori_caveats():
    ctx = make_ctx(FakeCache())
    out = rents.collect(ctx, ALL_UNITS)
    for unit in ALL_UNITS:
        for key in ("zori_latest", "zori_yoy", "zori_cagr_3y", "zori_month",
                    "zori_zip_coverage", "zori_zips_used"):
            value = out[unit.geoid][key]
            assert value.url == rents.ZORI_URL
            assert value.retrieved_at == RETRIEVED_AT
            assert "repeat-rent index of asking rents" in value.notes
            assert "smoothed" in value.notes
            assert "professionally managed" in value.notes
            assert "small ZIPs" in value.notes.lower() or "small zips" in value.notes.lower()
            if value.is_missing:
                assert value.missing_reason


def test_every_fmr_value_carries_the_fmr_caveat():
    ctx = make_ctx(FakeCache())
    out = rents.collect(ctx, ALL_UNITS)
    for unit in ALL_UNITS:
        for key in ("fmr_2br", "fmr_year", "zori_vs_fmr_ratio"):
            value = out[unit.geoid][key]
            assert "40th percentile" in value.notes
            assert "voucher" in value.notes


def test_every_unit_appears_with_every_declared_column():
    ctx = make_ctx(FakeCache())
    out = rents.collect(ctx, ALL_UNITS)
    assert set(out) == {u.geoid for u in ALL_UNITS}
    expected = {m.key for m in rents.METRICS} | {m.key for m in rents.CONTEXT_COLUMNS}
    for unit in ALL_UNITS:
        assert set(out[unit.geoid]) == expected


def test_metric_specs_match_the_contract():
    assert [m.key for m in rents.METRICS] == [
        "zori_latest", "zori_yoy", "zori_cagr_3y"
    ]
    assert [m.key for m in rents.CONTEXT_COLUMNS] == [
        "zori_month", "zori_zip_coverage", "zori_zips_used",
        "fmr_2br", "fmr_year", "zori_vs_fmr_ratio",
    ]
    for spec in rents.METRICS:
        assert spec.pillar == "rent"
        assert spec.higher_is_better is True
        assert spec.scored is True
    assert rents.METRICS[0].unit == "$"
    assert rents.METRICS[1].unit == "%"
    assert rents.METRICS[2].unit == "%"
    for spec in rents.CONTEXT_COLUMNS:
        assert spec.pillar == "rent"
        assert spec.scored is False


# --------------------------------------------------------------------------
# HUD FMR, both response shapes
# --------------------------------------------------------------------------
def test_hud_county_dict_shape_is_read_and_labelled():
    cache = FakeCache(fmr=FMR_DICT)
    values = rents.collect(make_ctx(cache), [UNIT_A])["2608130000"]

    assert values["fmr_2br"].value == pytest.approx(1250.0)
    assert values["fmr_year"].value == 2026
    assert "county-wide basicdata object" in values["fmr_2br"].notes
    # 1807.0 / 1250.0
    assert values["zori_vs_fmr_ratio"].value == pytest.approx(1.4456, abs=1e-4)

    hud_calls = [c for c in cache.calls if "huduser.gov" in c["url"]]
    assert hud_calls, "HUD endpoint was never called"
    call = hud_calls[0]
    # County entity id is the 5 digit FIPS plus 99999, 10 characters.
    assert call["url"].endswith("/2608199999")
    assert len(call["url"].rsplit("/", 1)[1]) == 10
    # The token travels in the header and never in the cache key.
    assert call["headers"]["Authorization"] == "Bearer SYNTHETIC-TEST-TOKEN"
    assert "SYNTHETIC-TEST-TOKEN" not in call["key"]
    assert call["params"] == {"year": 2027}


def test_hud_small_area_list_shape_uses_the_county_wide_entry():
    values = rents.collect(
        make_ctx(FakeCache(fmr=FMR_LIST_COUNTYWIDE)), [UNIT_A]
    )["2608130000"]
    assert values["fmr_2br"].value == pytest.approx(1300.0)
    assert "Small Area FMR list" in values["fmr_2br"].notes
    assert "county-wide entry" in values["fmr_2br"].notes


def test_hud_small_area_list_without_a_county_figure_is_missing_not_averaged():
    values = rents.collect(
        make_ctx(FakeCache(fmr=FMR_LIST_NO_COUNTYWIDE)), [UNIT_A]
    )["2608130000"]
    assert values["fmr_2br"].is_missing
    assert values["fmr_2br"].missing_reason == (
        "county is Small Area FMR; no single county figure returned"
    )
    # 1300 is the mean of 1500 and 1100. It must not appear anywhere.
    assert values["fmr_year"].is_missing
    assert values["zori_vs_fmr_ratio"].is_missing
    assert "Small Area FMR list" in values["fmr_2br"].notes


def test_hud_failure_does_not_stop_the_zori_columns():
    values = rents.collect(make_ctx(FakeCache(fmr=None)), [UNIT_A])["2608130000"]
    assert values["zori_latest"].value == pytest.approx(1807.0)
    assert values["fmr_2br"].is_missing
    assert "2608199999" in values["fmr_2br"].missing_reason


def test_unrecognised_hud_payload_raises_rather_than_guessing(tmp_path):
    broken = tmp_path / "hud_fmr_SYNTHETIC_broken.json"
    broken.write_text(json.dumps({"data": {"basicdata": "1250"}}))
    with pytest.raises(FetchError) as excinfo:
        rents.collect(make_ctx(FakeCache(fmr=broken)), [UNIT_A])
    assert "basicdata" in str(excinfo.value)


def test_without_a_hud_key_zori_still_loads_and_only_fmr_goes_missing(monkeypatch):
    """Zillow needs no key. HUD is only the cross-check, so it fails alone.

    This was wrong twice: first the key was checked after the ZORI pass, which
    threw away completed work, then it was checked before, which failed earlier
    and still took ZORI with it. Rent is 25% of the weighting and almost none
    of it depends on HUD.
    """
    monkeypatch.delenv("HUD_API_KEY", raising=False)
    out = rents.collect(make_ctx(FakeCache()), [UNIT_A])
    values = out[UNIT_A.geoid]

    assert values["zori_latest"].value is not None
    assert values["zori_yoy"].value is not None

    for key in ("fmr_2br", "fmr_year", "zori_vs_fmr_ratio"):
        assert values[key].is_missing
        assert "HUD_API_KEY" in values[key].missing_reason


# --------------------------------------------------------------------------
# House style
# --------------------------------------------------------------------------
def test_module_contains_no_em_or_en_dashes():
    source = Path(rents.__file__).read_text()
    assert chr(0x2014) not in source   # em dash
    assert chr(0x2013) not in source   # en dash
