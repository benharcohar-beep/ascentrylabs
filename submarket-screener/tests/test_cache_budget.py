"""A slow source must not be able to hold up the whole screen.

request_timeout is a per-socket timeout, so a download that keeps trickling
bytes never trips it. A 200MB file arriving slowly will therefore block a run
that is otherwise seconds from done, and it will do so to fill one column. The
budget bounds that, and the point of these tests is that it bounds it *during*
a transfer, not merely before one starts.
"""
from __future__ import annotations

import time

import pytest

from screener.cache import Cache, FetchError


class _SlowResponse:
    """Streams forever, one chunk at a time, like a very large slow file."""

    status_code = 200
    headers = {"Content-Type": "application/zip"}
    text = ""

    def __init__(self, delay: float = 0.02) -> None:
        self.delay = delay
        self.chunks_served = 0

    def iter_content(self, chunk_size: int = 1):
        while True:
            time.sleep(self.delay)
            self.chunks_served += 1
            yield b"x" * 1024


def test_a_transfer_already_under_way_is_still_interrupted(tmp_path, monkeypatch):
    cache = Cache(tmp_path, polite_delay=0.0)
    response = _SlowResponse()
    monkeypatch.setattr("screener.cache.requests.request",
                        lambda *a, **k: response)

    started = time.monotonic()
    with pytest.raises(FetchError) as caught:
        with cache.budget(0.3, label="schools"):
            cache.get("https://example.invalid/huge.zip", key="huge")
    elapsed = time.monotonic() - started

    assert elapsed < 5, "the budget did not interrupt an in-flight download"
    assert response.chunks_served > 1, "it gave up before the transfer started"
    message = str(caught.value)
    assert "schools" in message
    assert "budget" in message
    # It must say what was and was not affected, or a reader will assume the
    # whole run is compromised.
    assert "MISSING" in message


def test_a_partial_download_is_never_written_to_the_cache(tmp_path, monkeypatch):
    """An interrupted file must not be replayed later as if it were complete."""
    cache = Cache(tmp_path, polite_delay=0.0)
    monkeypatch.setattr("screener.cache.requests.request",
                        lambda *a, **k: _SlowResponse())
    with pytest.raises(FetchError):
        with cache.budget(0.3, label="schools"):
            cache.get("https://example.invalid/huge.zip", key="huge")
    assert not list(tmp_path.glob("*.bin")), "a truncated body was cached"
    assert not list(tmp_path.glob("*.meta.json"))


def test_no_budget_means_no_limit(tmp_path, monkeypatch):
    """The budget is opt in. Sources without one must behave exactly as before."""

    class Quick:
        status_code = 200
        headers = {"Content-Type": "text/plain"}
        text = ""

        def iter_content(self, chunk_size=1):
            yield b"hello"

    cache = Cache(tmp_path, polite_delay=0.0)
    monkeypatch.setattr("screener.cache.requests.request", lambda *a, **k: Quick())
    with cache.budget(None, label="rents"):
        resp = cache.get("https://example.invalid/small.txt", key="small")
    assert resp.text == "hello"


def test_a_nested_budget_cannot_extend_an_outer_one(tmp_path):
    """Otherwise a source could opt itself out of the limit it was given."""
    cache = Cache(tmp_path, polite_delay=0.0)
    with cache.budget(1, label="outer"):
        outer = cache._deadline
        with cache.budget(600, label="inner"):
            assert cache._deadline == outer
        assert cache._deadline == outer
    assert cache._deadline is None


# ---------------------------------------------------------------------------
# get_filtered_lines, which streams a national file and keeps one state's rows.
#
# The first live run of this failed with "a bytes-like object is required, not
# 'str'". requests only decodes a streamed body when the response declares a
# charset, and Census serves the .dat files as an octet stream with none, so
# every line arrives as bytes. The tests below run the bytes path, because a
# fixture that hands back str would have passed while the real thing broke.
# ---------------------------------------------------------------------------

REAL_HEADER = b"GEO_ID|B01003_E001|B01003_M001"
REAL_ROWS = [
    b"0100000US|334922499|-555555555",
    b"0600000US5500100275|2050|265",     # Wisconsin, wanted
    b"0600000US5500100300|1347|172",     # Wisconsin, wanted
    b"0600000US2600100275|999|50",       # Michigan, not wanted
    b"1600000US5500100|2024|276",        # Wisconsin place, wrong summary level
]


class _ByteStream:
    """Streams bytes lines, the way requests does for a body with no charset."""

    status_code = 200
    headers = {"Content-Type": "application/octet-stream"}
    text = ""

    def __init__(self, lines):
        self.lines = lines

    def iter_lines(self, chunk_size=1, decode_unicode=False):
        yield from self.lines


def _fake_get(lines):
    def _get(*a, **k):
        return _ByteStream(lines)
    return _get


def test_only_the_wanted_rows_and_the_header_survive(tmp_path, monkeypatch):
    cache = Cache(tmp_path, polite_delay=0.0)
    monkeypatch.setattr("screener.cache.requests.get",
                        _fake_get([REAL_HEADER] + REAL_ROWS))
    resp = cache.get_filtered_lines(
        "https://example.invalid/acsdt5y2024-b01003.dat",
        key="acs", prefixes=("0600000US55",),
    )
    lines = resp.text.strip().splitlines()
    assert lines[0] == "GEO_ID|B01003_E001|B01003_M001"
    assert lines[1:] == [
        "0600000US5500100275|2050|265",
        "0600000US5500100300|1347|172",
    ]


def test_the_header_is_kept_even_though_it_matches_no_prefix():
    """Without it the extract cannot be parsed, and the failure would look
    like a layout change rather than a dropped line."""
    # Covered by the assertion above; kept separate so the reason is recorded.
    assert not REAL_HEADER.startswith(b"0600000US55")


def test_a_str_body_is_handled_too(tmp_path, monkeypatch):
    """Some servers do declare a charset. Both paths must work."""
    cache = Cache(tmp_path, polite_delay=0.0)
    monkeypatch.setattr("screener.cache.requests.get",
                        _fake_get([line.decode() for line in [REAL_HEADER] + REAL_ROWS]))
    resp = cache.get_filtered_lines(
        "https://example.invalid/x.dat", key="acs2", prefixes=("0600000US55",))
    assert "0600000US5500100275|2050|265" in resp.text
    assert "2600100275" not in resp.text


def test_several_states_can_be_kept_at_once(tmp_path, monkeypatch):
    """A market can straddle a state line, and the file is national anyway."""
    cache = Cache(tmp_path, polite_delay=0.0)
    monkeypatch.setattr("screener.cache.requests.get",
                        _fake_get([REAL_HEADER] + REAL_ROWS))
    resp = cache.get_filtered_lines(
        "https://example.invalid/y.dat", key="acs3",
        prefixes=("0600000US55", "0600000US26"))
    assert "0600000US2600100275|999|50" in resp.text


def test_the_extract_is_replayed_from_cache_without_downloading_again(tmp_path, monkeypatch):
    cache = Cache(tmp_path, polite_delay=0.0)
    calls = []

    def counting(*a, **k):
        calls.append(1)
        return _ByteStream([REAL_HEADER] + REAL_ROWS)

    monkeypatch.setattr("screener.cache.requests.get", counting)
    first = cache.get_filtered_lines("https://example.invalid/z.dat", key="acs4",
                                     prefixes=("0600000US55",))
    second = cache.get_filtered_lines("https://example.invalid/z.dat", key="acs4",
                                      prefixes=("0600000US55",))
    assert len(calls) == 1, "it downloaded the national file twice"
    assert second.from_cache and not first.from_cache
    assert first.text == second.text


def test_the_cached_extract_is_far_smaller_than_the_download(tmp_path, monkeypatch):
    """The point of the whole method. The sidecar records both so the saving
    is auditable rather than asserted."""
    import json

    cache = Cache(tmp_path, polite_delay=0.0)
    noise = [b"0600000US1200100275|1|1"] * 500
    monkeypatch.setattr("screener.cache.requests.get",
                        _fake_get([REAL_HEADER] + REAL_ROWS + noise))
    cache.get_filtered_lines("https://example.invalid/w.dat", key="acs5",
                             prefixes=("0600000US55",))
    meta = json.loads(next(tmp_path.glob("*.meta.json")).read_text())
    assert meta["lines_kept"] == 3
    assert meta["bytes"] < meta["bytes_downloaded"] / 10
