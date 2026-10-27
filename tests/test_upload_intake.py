"""Regression coverage for 33–70 MB Streamlit intake memory/safety."""
import io
from pathlib import Path

import pytest

from services.api import upload_intake


class Upload(io.BytesIO):
    def __init__(self, value, name="1014.mp4"):
        super().__init__(value)
        self.name=name

    def getvalue(self):
        raise AssertionError("Spooling must not make a full bytes copy")

    def read(self, n=-1):
        assert 0 < n <= 1024 * 1024, "Only bounded chunks may be read"
        return super().read(n)


def test_33mb_upload_spools_without_duplicate_getvalue(tmp_path):
    payload=b"mp4-test-bytes" * (33 * 1024 * 1024 // len(b"mp4-test-bytes"))
    source=Upload(payload)
    signature=upload_intake.fingerprint_upload(source)
    assert signature[0]=="1014.mp4"
    assert signature[1]==len(payload)
    source_path=upload_intake.spool_uploaded_file(source,tmp_path,signature)
    assert source_path.name=="source.mp4"
    assert source_path.stat().st_size==len(payload)
    assert source_path.read_bytes()==payload
    assert source.tell()==0


def test_path_traversal_in_browser_filename_is_ignored(tmp_path):
    source=Upload(b"video contents", "../../private/path/1014.mkv")
    signature=upload_intake.fingerprint_upload(source)
    source_path=upload_intake.spool_uploaded_file(source,tmp_path,signature)
    assert signature[0]=="1014.mkv"
    assert source_path.parent==tmp_path
    assert source_path.name=="source.mkv"


def test_corruption_cleans_partial_file_and_does_not_mark_success(tmp_path):
    source=Upload(b"first", "road.mp4")
    signature=upload_intake.fingerprint_upload(source)
    source.seek(0)
    source.write(b"other")
    with pytest.raises(ValueError,match="verification"):
        upload_intake.spool_uploaded_file(source,tmp_path,signature)
    assert not list(tmp_path.glob("source*"))


def test_invalid_type_and_size_rejected_without_spooling(tmp_path,monkeypatch):
    monkeypatch.setattr(upload_intake,"MAX_SOURCE_BYTES",4)
    with pytest.raises(ValueError,match="70 MB"):
        upload_intake.fingerprint_upload(Upload(b"12345"))
    with pytest.raises(ValueError,match="Unsupported"):
        upload_intake.fingerprint_upload(Upload(b"123","bad.exe"))
    assert not list(tmp_path.iterdir())
