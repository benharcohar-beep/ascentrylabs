"""A body that is not data must not be left in the cache.

The Census API answers a rejected key with HTTP 200 and an HTML page. Without
this behaviour that page is stored as if it were data and replayed for the full
90 day TTL, so activating the key appears to change nothing.
"""
from __future__ import annotations

from pathlib import Path

from screener.cache import Cache


def test_forget_removes_both_files(tmp_path: Path):
    cache = Cache(tmp_path)
    body, meta = cache._entry_paths("some_key")
    body.write_bytes(b"not really data")
    meta.write_text('{"key": "some_key"}')

    assert cache.forget("some_key") is True
    assert not body.exists()
    assert not meta.exists()


def test_forget_is_safe_when_nothing_is_cached(tmp_path: Path):
    cache = Cache(tmp_path)
    assert cache.forget("never_stored") is False


def test_a_forgotten_entry_is_refetched(tmp_path: Path, monkeypatch):
    """The point of the whole thing: the next call must go back to the network."""
    cache = Cache(tmp_path)
    body, meta = cache._entry_paths("k")
    body.write_bytes(b"<html><title>Invalid Key</title></html>")
    meta.write_text('{"key": "k", "retrieved_at": "2099-01-01T00:00:00Z"}')

    # While it is cached, offline mode serves it happily.
    offline = Cache(tmp_path, offline=True)
    assert b"Invalid Key" in offline.get("https://example.invalid", key="k").body

    cache.forget("k")

    # Once forgotten there is nothing to serve, so offline mode has to say so
    # rather than hand back the poisoned page.
    import pytest
    from screener.cache import FetchError

    with pytest.raises(FetchError):
        Cache(tmp_path, offline=True).get("https://example.invalid", key="k")
