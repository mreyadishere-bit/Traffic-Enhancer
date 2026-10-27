"""Truthful recovery states for ephemeral Streamlit overlay videos.

The report may say "completed" while the derived MP4 has disappeared after
a free-host restart. Never present such cases as still processing.
"""
from __future__ import annotations


def overlay_state(*, ready: bool, video_exists: bool,
                  source_exists: bool, job_active: bool, attempted: bool,
                  last_status: str | None) -> str:
    if video_exists:
        return "available"
    if not ready:
        return "case_not_ready"
    if job_active:
        return "rendering"
    if not source_exists:
        return "source_missing"
    if last_status == "failed":
        return "failed"
    if attempted:
        return "needs_retry"
    return "auto_rebuild"
