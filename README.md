# Traffic Enhancer

**Turning Every Drive into an Opportunity for Safer Roads.**

An early-stage road evidence platform. The first **runnable web vertical slice** accepts real dashcam videos, checks file integrity, extracts an actual frame using FFmpeg, optionally runs YOLO/BoT-SORT video tracking, speech transcription, Qwen2.5-VL visual analysis and plate OCR when the required models are configured, and produces a preliminary PDF report.

> **Current limitations:** Not an official reporting service. No automatic camera-to-phone sync, real-device-verified mobile release or legally verified traffic-violation detector is implemented. Tracking and OCR need independently configured model weights. No fabricated detections are used. The operator-key login is for local development only.

## Start locally

Install **Python 3.11+** and **FFmpeg/ffprobe** first, then:

~~~bash
git clone https://github.com/mreyadishere-bit/Traffic-Enhancer.git
cd Traffic-Enhancer
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
# Set your own strong API key in your terminal:
export TE_API_KEY="replace-with-long-random-key"
python -m uvicorn services.api.main:app --reload
~~~

For Windows PowerShell, replace the export command with:

~~~powershell
$env:TE_API_KEY="replace-with-long-random-key"
~~~

Open [http://localhost:8000](http://localhost:8000), enter the configured operator key and upload an MP4, MOV or MKV video (1–180 seconds, max 150 MB). The application persists the original bytes and SHA-256 hash in the ignored \`data/\` directory. The REST endpoints and interactive OpenAPI documentation are at [http://localhost:8000/docs](http://localhost:8000/docs).

The API default is \`dev-only-change-me\` in development **only**. Never expose it to the internet.

## Optional real AI

~~~bash
pip install -r requirements-ai.txt
export TE_YOLO_MODEL="/absolute/path/to/trusted-yolo-weights.pt"
export TE_ASR_MODEL="/absolute/path/to/local-whisper-model"
~~~

Optional YOLO/BoT-SORT now tracks vehicles across sampled video frames. Faster-whisper transcribes voice descriptions; conservative parsing keeps the DRIVER'S CLAIM distinct from visually observed events. Optional Qwen2.5-VL-3B-Instruct reasons over actual timestamped video frames and emits **unverified review candidates**. Optional Egyptian-plate detector weights plus EasyOCR produce candidate strings only. No model determines legal guilt.

For Qwen2.5-VL: install `pip install -r requirements-vlm.txt`, set `TE_ENABLE_QWEN=1`, `TE_QWEN_MODEL=Qwen/Qwen2.5-VL-3B-Instruct`; supply cached model weights or explicitly set `TE_QWEN_ALLOW_DOWNLOAD=1`. Large weights require substantial RAM/GPU resources. For OCR also install `pip install -r requirements-ocr.txt` and supply an **Egyptian-plate-specific** detector model at `TE_PLATE_MODEL`. Specify your own evaluated YOLO weights via `TE_YOLO_MODEL` and a locally available Whisper model via `TE_ASR_MODEL`. Unconfigured/failed stages are labeled rather than guessed. Read [AI runtime](docs/AI_RUNTIME.md).

## Test

~~~bash
python -m pytest -q
~~~

GitHub Actions installs FFmpeg and executes tests including a generated MP4 upload, persisted evidence, frame extraction, authenticated playback, and PDF generation.

## Docker for private development

Create a \`.env\` file from \`.env.example\`, set a **strong** \`TE_API_KEY\`, then:

~~~bash
docker compose up --build -d
~~~

The Compose deployment binds only to **127.0.0.1:18090**. It never uses public ports 80 or 443 or modifies other projects' containers. **Do not publish the app before genuine user authentication, isolated processing, quotas, retention policies, and other protections are implemented.**

## Capability status

| Feature | Status |
|---|---|
| Responsive evidence dashboard | Implemented |
| Actual authenticated video upload, integrity hash, metadata | Implemented for development |
| FFmpeg keyframe extraction and source preview | Implemented |
| PDF preliminary report export | Implemented |
| Multi-frame vehicle detection and tracking | Optional YOLO + BoT-SORT; real-footage validation required |
| Audio transcription | Implemented with optional faster-whisper model; not benchmarked |
| Qwen2.5-VL visual scene analysis | Optional real model inference; needs sufficient hardware and weights |
| Egyptian plate OCR | Optional model + OCR candidate pipeline; Egyptian-trained weights required |
| Traffic violation conclusions | Only tentative model candidates; no verified legal offense detector |
| Automatic DDPAI import to our app | Unverified; not implemented |
| Android / iPhone Expo source foundation | Implemented; real-device tests and production integration pending |
| Full multi-user security / production workflow | Not implemented |

Mobile source: [apps/mobile](apps/mobile/README.md). Read [system architecture](docs/ARCHITECTURE.md), [DDPAI feasibility](docs/CAMERA_FEASIBILITY.md), and [planned camera interface](integrations/dashcams/README.md).
