# Fix missing YOLO or faster-whisper (Windows)

Errors like \`ModuleNotFoundError: No module named 'ultralytics'\` and
\`No module named 'faster_whisper'\` mean you started the lightweight core
backend without installing the optional AI libraries. They are **not**
failures of the video upload.

## Easiest: two clicks, no typing commands

1. Close the previously running \`python -m uvicorn\` server with **Ctrl+C**.
2. In your Traffic-Enhancer folder, double-click **Start-Traffic-Enhancer-AI.cmd**.
   The first run checks and installs Python AI libraries in the project's
   \`.venv\`, configures \`yolo11n.pt\` for CPU and multilingual Whisper
   \`base\` with int8 computation, and opens the browser.
3. First use may download YOLO and Whisper model weights from their
   official model sources. This requires network access and enough disk space.
4. Open your existing case from **Incident library** and select **Re-run
   analysis**. No need to upload the original recording again.

**Important:** Your original manually started \`uvicorn\` process may have used
a different Python interpreter than the \`.venv\` used by the launcher.
Do not run both at the same time. If you want to continue using PowerShell
manually, install packages with the same Python you use to run the server:

~~~powershell
python -m pip install -r requirements-ai.txt
$env:TE_YOLO_MODEL="yolo11n.pt"
$env:TE_ASR_MODEL="base"
$env:TE_ASR_ALLOW_DOWNLOAD="1"
$env:TE_ASR_DEVICE="cpu"
$env:TE_ASR_COMPUTE_TYPE="int8"
python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload
~~~

### Qwen2.5-VL is a different stage

YOLO detects/tracks vehicles. Whisper transcribes audio. Neither provides
multimodal Qwen reasoning. GitHub **Codespaces secrets are not available**
to Windows PowerShell. To activate Qwen on Windows, create a fresh OpenRouter
key and set the following variables in the **same local process** before
starting the API:

~~~powershell
$env:TE_QWEN_API_KEY = Read-Host "Enter your new OpenRouter key"
$env:TE_ENABLE_QWEN = "1"
$env:TE_QWEN_API_BASE = "https://openrouter.ai/api/v1"
$env:TE_QWEN_MODEL = "qwen/qwen-2.5-vl-7b-instruct:free"
~~~

Never save API keys to your repository or screenshots. An exposed key must be
revoked/replaced. Qwen's free endpoint may be unavailable or rate limited;
a configured stage is not proof of a successfully completed inference.

### Expectations

- A video's audio needs a real audio track for Whisper to work.
- A detector returning \`completed\` confirms execution only, not accuracy.
- License plate OCR still requires an evaluated Egyptian license-plate
  detection model. No governmental traffic/offense verification is present.
- Repeated re-analysis is faster because model weights are reused in the
  running backend process. CPU analysis of longer videos can remain slow.
