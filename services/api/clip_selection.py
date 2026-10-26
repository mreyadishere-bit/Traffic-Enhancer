"""Pure validation of source clip selection.

The UI uses this before scheduling a video upload. The FastAPI backend
independently validates against actual FFprobe metadata.
"""
import math


def choose_clip_interval(duration: float, entire_source: bool,
                         start: float, end: float) -> tuple[float, float, bool]:
    duration = float(duration)
    if not math.isfinite(duration) or duration < 1:
        raise ValueError("The uploaded video has no usable duration.")
    if entire_source:
        if duration > 180:
            raise ValueError(
                "The full recording exceeds 180 seconds. Select a section instead."
            )
        return 0.0, duration, True

    start, end = float(start), float(end)
    if not math.isfinite(start) or not math.isfinite(end):
        raise ValueError("Start and end must be finite numbers.")
    if start < 0 or end <= start:
        raise ValueError("End must be later than start.")
    if end > duration + 1e-6:
        raise ValueError("Selection ends after the source recording.")
    if end - start < 1:
        raise ValueError("Select at least one second.")
    if end - start > 180 + 1e-6:
        raise ValueError("Select at most 180 seconds.")
    return start, end, False
