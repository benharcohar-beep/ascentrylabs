"""No em dashes or en dashes anywhere in this project.

A standing rule for everything this repository produces. It is enforced here
rather than trusted, because a shell heredoc will happily turn a backslash-u
escape into the real character on the way to disk, which is exactly how one got
in before. Note that grep -P with a brace escape does not reliably catch these
on every machine, so the check is done in Python.
"""
from __future__ import annotations

from pathlib import Path

EN_DASH = chr(0x2013)
EM_DASH = chr(0x2014)

PROJECT = Path(__file__).resolve().parent.parent
SKIP_PARTS = {".venv", ".git", "__pycache__", "node_modules", "data", "output"}
CHECK_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".csv", ".txt", ".html", ".json", ".cfg"}


def _files_to_check() -> list[Path]:
    out = []
    for path in PROJECT.rglob("*"):
        if not path.is_file():
            continue
        if SKIP_PARTS & set(path.relative_to(PROJECT).parts):
            continue
        if path.suffix.lower() in CHECK_SUFFIXES:
            out.append(path)
    return out


def test_no_em_or_en_dashes_in_the_repository():
    offenders = []
    for path in _files_to_check():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if EN_DASH in line or EM_DASH in line:
                offenders.append(f"{path.relative_to(PROJECT)}:{lineno}: {line.strip()[:120]}")
    assert not offenders, "long dashes found:\n" + "\n".join(offenders)


def test_the_checker_can_actually_see_a_dash(tmp_path: Path):
    # Guards against the check silently passing because the scan is broken.
    sample = tmp_path / "sample.md"
    sample.write_text(f"a {EM_DASH} b\n", encoding="utf-8")
    assert EM_DASH in sample.read_text(encoding="utf-8")
