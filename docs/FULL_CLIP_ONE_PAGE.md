# Full-duration annotated video & one-page operation

The old five-image technical montage (5 seconds) is **not** the selected
clip. The new automatic `<case>.tracked.mp4` is generated from the actual
selected MP4, with a checked output duration within 0.13 seconds of that
source clip.

**Practical workflow:** open Streamlit -> New analysis -> upload -> optionally
trim -> Analyze. The backend returns the new case ID immediately and starts
processing in the background worker. Streamlit polls real database status
every three seconds and presents the result under the upload controls on
the same page; no separate Evidence Studio navigation is needed.

**Inference performance:** CPU-only YOLO samples every output video frame
at 3 fps for clips <=45 seconds, 2 fps up to 120 seconds, and 1 fps for
longer clips, to bound CPU load on Streamlit Community Cloud. The resulting
video preserves the full timeline and any audio at browser-friendly 10 fps.
Intermediate frames repeat recent sample images/boxes, not predictions; this
is NOT high-fps continuous tracking or proof of a traffic violation.

Older cases with only the five-second montage are automatically upgraded on
view using local CPU YOLO, without Qwen/Groq API requests. The preview
appears when encoding completes. Derived files remain temporary.

Full-video inference on free Streamlit CPU might be slow, restart, or fail.
Progress updates report actual pipeline stages and processed frame counts.
Physical speed and distance are still unavailable without calibrated
ground-plane geometry and reliable multi-object tracking.

Never upload private or identifying videos to this public no-login demo.
