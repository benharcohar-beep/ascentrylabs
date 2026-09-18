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
