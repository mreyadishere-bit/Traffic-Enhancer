# Traffic Enhancer — Streamlit Community Cloud

This repo now includes a **native Streamlit browser UI** that invokes the existing
FastAPI/FFmpeg analysis pipeline without running a separate publicly exposed API.

### Deploy once (all from your browser; no CMD, no credit card)

1. Make sure this feature has passed tests and been merged into \`main\`.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in using GitHub.
3. Click **Create app → Yup, I have an app**.
4. Select:
   - **Repository:** \`mreyadishere-bit/Traffic-Enhancer\`
   - **Branch:** \`main\`
   - **Main file path:** \`streamlit_app.py\`
   - **App URL:** choose an available subdomain, e.g. \`traffic-enhancer-lab\`.
5. In **Advanced settings → Secrets**, paste TOML values like:

~~~toml
TE_QWEN_API_KEY = "REPLACE_WITH_NEW_OPENROUTER_KEY"
TE_QWEN_API_BASE = "https://openrouter.ai/api/v1"
TE_QWEN_MODEL = "qwen/qwen-2.5-vl-7b-instruct:free"
TE_QWEN_FRAMES = "2"
TE_GROQ_API_KEY = "REPLACE_WITH_NEW_GROQ_KEY"
TE_GROQ_ASR_MODEL = "whisper-large-v3-turbo"
~~~

All values above are **examples, not usable secrets**. Create fresh keys:
[OpenRouter keys](https://openrouter.ai/settings/keys) and
[Groq keys](https://console.groq.com/keys). Keys previously shared in chat screenshots must be revoked.
No visitor password or TE_API_KEY is required in Streamlit. The server generates
its own random internal FastAPI key. An existing TE_API_KEY in Streamlit secrets
can be deleted without affecting the public demo.
You can omit the Groq or OpenRouter credentials to disable that stage.
Never commit \`.streamlit/secrets.toml\` or put secrets in frontend code.

6. Click **Deploy** and visit the resulting Streamlit URL. The app opens
   immediately with **no login or password prompt**.

### Updates without manual deployment

Every change merged or pushed to the configured \`main\` branch gets picked up
and redeployed automatically by Streamlit Cloud. You do not need PowerShell,
Windows, GitHub Codespaces, Render, Blitz or a manually running FastAPI port.

### Real capabilities and important limitations

- Preserves the existing FastAPI workflow and PDF export, and shows actual
  model state/error messages instead of fake analysis results.
- Uses remote Qwen2.5-VL and optional Groq Whisper when secrets are valid.
- CPU-only **YOLOv8n vehicle detection** and a **generic pretrained YOLO26n ONNX plate detector (Egypt unvalidated)**
  now run in Streamlit via `onnxruntime`. Detected plate crops are read
  tentatively by Arabic + English Tesseract; uncertainty is explicitly shown.
  First use downloads public ONNX weights; accuracy and free-cloud reliability
  are not independently verified. See [CPU AI details](CLOUD_CPU_VISION.md).
- Streamlit Community Cloud memory/CPU are limited and resources aren't a
  permanent file/database vault. The app can go to sleep or restart at any
  time, wiping local SQLite/video files. **Do not upload sensitive third-party
  footage or rely on this deployment for evidence preservation.**
- Video uploads are capped at 70 MB. Native Streamlit first transfers the source
  to its server-side memory. On successful receipt, the app stages it to a private
  temporary file using 1 MiB chunks; FFprobe then reads duration, after which
  the optional trim controls appear. The original path is reused for preview and
  background submission to avoid additional full-size Python bytes allocations.
  If the file thumbnail keeps spinning and the app still says "Choose a video",
  this means Streamlit has not delivered the file to Python; AI/FFprobe have NOT
  started. Click **Reset stuck upload / choose a file again**, then reselect the
  clip. If still stuck, reboot the Streamlit Cloud app and try a small MP4 to
  isolate a Cloud/network upload issue. Reset does not erase saved incident IDs.
  The app cannot guarantee a fix for underlying browser/network upload failure.
- **Optional clip trim:** use the two-handle timeline or exact START/END
  numeric inputs to select any 1–180-second interval; the Streamlit preview
  starts and stops at the chosen timestamps when the browser can play MP4.
  Alternatively choose the full video if its duration is at most 180 seconds.
  The backend keeps the original source and trims accurately with FFmpeg.
  For large recordings, upload a smaller source copy for faster transfers.
- Public no-password demo. Each browser session sees only cases it created,
  not the shared backend's global case index. This is NOT a private vault;
  temporary files are still held on the shared server and can disappear.
  Upload only nonsensitive videos; browser sessions can lose case links.
- Anonymous access can consume your API quota. The app limits analyses to
  four per session and 20 per 24 hours per app process, but these are not
  a substitute for production rate-limiting and authenticated case storage.
- No official plate registry or government traffic system is connected.
  Suggested events are unverified.

When production requirements matter, use a dedicated deployment with secure
storage/authentication and a GPU worker. The original local FastAPI app
continues to function unchanged.

Documentation: https://docs.streamlit.io/deploy/streamlit-community-cloud/
