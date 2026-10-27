"""Memory-conscious, bounded intake helpers for Streamlit uploaded road clips.

The Streamlit widget itself uploads into RAM before these functions run.
Once received, spool to a private per-session temporary directory using a
bounded buffer, rather than creating another full-size Python bytes object.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


SUPPORTED_SUFFIXES = {".mp4", ".mov", ".mkv"}
MAX_SOURCE_BYTES = 70 * 1024 * 1024


def fingerprint_upload(upload) -> tuple[str, int, str]:
    """Hash the already-uploaded BytesIO without calling getvalue()/copying it."""
    name = Path(str(upload.name)).name
    if Path(name).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("Unsupported video format. Use MP4, MOV, or MKV.")
    view = upload.getbuffer()
    try:
        length = len(view)
        if not length or length > MAX_SOURCE_BYTES:
            raise ValueError("Video must be between 1 byte and 70 MB.")
        return name, length, hashlib.sha256(view).hexdigest()
    finally:
        view.release()


def spool_uploaded_file(upload, folder: Path, signature: tuple[str, int, str]) -> Path:
    """Copy a received Streamlit upload to a unique app-controlled local path.

    Never use the supplied filename as a filesystem path. Bound writes and
    verify the digest/size to avoid partial staging if the source is truncated.
    """
    name, expected_length, expected_digest = signature
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Unsupported video extension.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / ("source" + suffix)
    partial = folder / ("source" + suffix + ".partial")
    digest = hashlib.sha256()
    written = 0
    try:
        upload.seek(0)
        with partial.open("wb") as handle:
            while True:
                block = upload.read(1024 * 1024)
                if not block:
                    break
                written += len(block)
                if written > MAX_SOURCE_BYTES:
                    raise ValueError("Video exceeds the 70 MB limit.")
                digest.update(block)
                handle.write(block)
        if written != expected_length or digest.hexdigest() != expected_digest:
            raise ValueError("Video transfer verification failed. Retry upload.")
        partial.replace(dest)
    finally:
        upload.seek(0)
        partial.unlink(missing_ok=True)
    return dest
