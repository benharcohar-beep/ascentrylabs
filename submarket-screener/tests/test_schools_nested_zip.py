"""NCES publishes the CCD flat files inside a zip inside a zip.

The first live run found this: the download succeeded, the archive opened, and
it held ccd_lea_052_2122_l_1a_071722_CSV.zip and ..._SAS.zip rather than any
table. The reader gave up there and the whole school pillar went MISSING, after
spending two minutes downloading the file it then could not read.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from screener.cache import FetchError
from screener.sources.schools import _first_csv_member


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return buf.getvalue()


def test_a_plain_zip_still_works():
    data = _zip({"ccd_lea_029.csv": b"LEAID,NAME\n1,One\n"})
    assert b"LEAID" in _first_csv_member(data, label="directory")


def test_the_real_nces_shape_is_read_through_two_levels():
    inner_csv = _zip({"ccd_lea_052_2122_l_1a_071722.csv": b"LEAID,STUDENT_COUNT\n1,500\n"})
    inner_sas = _zip({"ccd_lea_052_2122_l_1a_071722.sas7bdat": b"\x00binary"})
    outer = _zip({
        "ccd_lea_052_2122_l_1a_071722_SAS.zip": inner_sas,
        "ccd_lea_052_2122_l_1a_071722_CSV.zip": inner_csv,
    })
    assert b"STUDENT_COUNT" in _first_csv_member(outer, label="membership")


def test_the_csv_archive_is_preferred_over_the_sas_one():
    """Not by alphabetical luck. A SAS file would read as an unusable table."""
    inner_csv = _zip({"data.csv": b"LEAID\n1\n"})
    inner_sas = _zip({"data.txt": b"this is the SAS extract, not the data"})
    outer = _zip({
        "AAA_SAS.zip": inner_sas,   # sorts first by name
        "zzz_CSV.zip": inner_csv,
    })
    assert _first_csv_member(outer, label="membership") == b"LEAID\n1\n"


def test_a_zip_holding_nothing_readable_still_names_what_it_held():
    outer = _zip({"readme.pdf": b"%PDF-1.4", "notes.docx": b"PK"})
    with pytest.raises(FetchError) as caught:
        _first_csv_member(outer, label="membership")
    assert "readme.pdf" in str(caught.value)


def test_nesting_cannot_loop_forever():
    """A zip that contains itself must fail, not hang or blow the stack."""
    data = _zip({"a.zip": _zip({"b.zip": _zip({"c.zip": _zip({"d.zip": b"x"})})})})
    with pytest.raises(FetchError):
        _first_csv_member(data, label="membership")
