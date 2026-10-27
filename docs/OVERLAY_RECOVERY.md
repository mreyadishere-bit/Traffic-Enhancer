# Missing video after Streamlit Cloud reboot — recovery

The full YOLO MP4 lives in the Streamlit application's **temporary filesystem**.
Its SQLite report can still say full_length_video.status = "completed"
even after the MP4 file disappears. In the older Streamlit UI this showed
"Preparing the selected recording's full-duration overlay" indefinitely;
a one-shot session flag prevented automatic retriggering.

The viewer now checks that the MP4 and original video actually exist:
- If the output exists, it displays the full-length annotated player.
- If output is absent but the original clip is available, it starts **one**
  automatic local overlay rebuild. The 3-second status poll follows the real
  render stage; requests to OpenRouter/Groq are not repeated.
- If rendering fails or its one-time task ends with no usable file, a
  specific error and **Retry full-length overlay** button are shown.
  No silent infinite spinner, no rapid automatic retry loops.
- If the source clip is absent, the app explicitly asks for a reupload;
  neither the old YOLO boxes nor a report hash can reconstruct the source.
- Switching between cases will not overwrite an already running render job.

This improves error recovery **but is not persistent cloud storage**.
True cross-restart preservation of source and derived evidence still
requires a separately secured object-storage backend.
The no-login demo is not suitable for identifying road recordings.
