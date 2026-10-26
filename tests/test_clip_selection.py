"""Clipping bounds must remain accurate before a video is submitted."""
import math
import pytest
from services.api.clip_selection import choose_clip_interval


def test_short_selected_clip_preserves_exact_source_timestamps():
    assert choose_clip_interval(211.0, False, 63.0, 86.3) == (63.0, 86.3, False)


def test_full_video_remains_optional():
    assert choose_clip_interval(32.5, True, 0.0, 10.0) == (0.0, 32.5, True)


@pytest.mark.parametrize("duration,start,end", [
    (211.0, 2.0, 211.1),  # past the source's actual end
    (211.0, 40.0, 40.5),   # too short to analyze
    (211.0, 0.0, 190.0),   # too long for the 180 s cap
    (211.0, 45.0, 45.0),   # empty
    (211.0, -1.0, 10.0),   # negative
    (211.0, float("nan"), 10.0),
])
def test_invalid_ranges_rejected(duration,start,end):
    with pytest.raises(ValueError):
        choose_clip_interval(duration, False, start, end)


def test_full_long_video_requires_selected_clip():
    with pytest.raises(ValueError, match="exceeds 180 seconds"):
        choose_clip_interval(211.0, True, 0.0, 211.0)
