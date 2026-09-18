"""Tests for the interactive key setup helper.

These pin the specific ways pasting a key into a terminal goes wrong, because
every one of them has actually happened: a token that wrapped across lines when
copied out of a browser dialog, a Bearer prefix copied along with it, quotes
added by an editor, and an abbreviated example string pasted as if it were a
real key.
"""
from __future__ import annotations

import setup_keys


def test_whitespace_and_line_breaks_are_stripped():
    wrapped = "eyJ0eXAiOiJKV1Qi\nLCJhbGciOiJIUzI1NiJ9.\n  eyJhdWQiOiI2In0.abc"
    assert setup_keys.clean(wrapped) == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI2In0.abc"


def test_bearer_prefix_is_removed():
    assert setup_keys.clean("Bearer abc123") == "abc123"
    assert setup_keys.clean("bearer abc123") == "abc123"


def test_quotes_are_removed():
    assert setup_keys.clean('"abc123"') == "abc123"
    assert setup_keys.clean("'abc123'") == "abc123"


def test_an_abbreviated_example_is_rejected():
    assert setup_keys.looks_like_placeholder("eyJ0eXAiOiJKV1QiLCJhbGci...")
    assert setup_keys.looks_like_placeholder("<paste your key here>")
    assert not setup_keys.looks_like_placeholder("a30f75cc609b473996db5dd82d3e24bb")


def test_key_shapes():
    census = next(k for k in setup_keys.KEYS if k["name"] == "CENSUS_API_KEY")
    hud = next(k for k in setup_keys.KEYS if k["name"] == "HUD_API_KEY")

    assert census["shape"].match("a" * 40)
    assert not census["shape"].match("not-hex-at-all")

    good_jwt = "eyJ0eXAiOiJKV1Qi.eyJhdWQiOiI2In0.sig_with-chars"
    assert hud["shape"].match(good_jwt)
    # Two segments is a truncated paste, which must not pass silently.
    assert not hud["shape"].match("eyJ0eXAiOiJKV1Qi.eyJhdWQiOiI2In0")


def test_written_env_puts_each_key_on_one_line(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_keys, "ENV_PATH", tmp_path / ".env")
    token = "eyJ0eXAi.eyJhdWQi.sig"
    setup_keys.write({
        "CENSUS_API_KEY": "a" * 40,
        "BLS_API_KEY": "b" * 32,
        "HUD_API_KEY": token,
    })
    lines = (tmp_path / ".env").read_text(encoding="utf-8").splitlines()
    assert f"HUD_API_KEY={token}" in lines
    assert f"CENSUS_API_KEY={'a' * 40}" in lines
    assert sum(1 for line in lines if line.startswith("HUD_API_KEY=")) == 1


def test_a_skipped_key_is_written_as_empty_not_omitted(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_keys, "ENV_PATH", tmp_path / ".env")
    setup_keys.write({"CENSUS_API_KEY": "a" * 40})
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "BLS_API_KEY=" in text
    assert "HUD_API_KEY=" in text


def test_existing_keys_are_read_back(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nCENSUS_API_KEY=abc\nBLS_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr(setup_keys, "ENV_PATH", env)
    found = setup_keys.read_existing()
    assert found == {"CENSUS_API_KEY": "abc"}


def test_masking_never_prints_a_whole_key():
    secret = "a" * 40
    masked = setup_keys.mask(secret)
    assert secret not in masked
    assert masked.startswith("aaaaaa")
