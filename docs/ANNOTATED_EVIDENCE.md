# Annotated sampled evidence and image-plane motion

Evidence studio shows the **unaltered original recording** and a separate
**annotated sampled-frame video**. Each image in this short montage is
an actual decoded timestamped source frame with bounding boxes from YOLO
at that same timestamp. Each image is held for one second of slideshow
playback and is explicitly not continuous full-video tracking.

The derived annotated JPEG and sampled MP4 can be viewed/downloaded.
Vehicle type, provisional ID, confidence and plate region outlines are shown.
Measured pixel path length and pixel movement per source second are shown
only for provisional IDs matched on two or more observations, with a CSV export.

Metric speed in km/h and distance in metres intentionally remain N/A.
Pixel motion cannot be converted to physical speed without verified camera
calibration, ground-plane scale, accurate timestamps and stable tracking.
Sparse IoU IDs can switch or be wrong, and no citation should result.

OCR fragments without at least two Arabic letters and three digits are
filtered instead of being presented as full Egyptian plate numbers.

The retired OpenRouter legacy Qwen2.5 free slug can return 404. On that
specific slug only, the app retries the available free image-capable
model qwen/qwen3.8-27b:free at OpenRouter. No paid fallback.
Set TE_QWEN_MODEL to qwen/qwen3.8-27b:free in Streamlit secrets for
new processing; even free models can be rate-limited or unavailable.

Existing stored cases must use Re-run AI analysis to create new artifacts.
