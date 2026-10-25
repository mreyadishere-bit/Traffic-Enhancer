# Traffic Enhancer

**Turning Every Drive into an Opportunity for Safer Roads.**

An early-stage road evidence platform. The first **runnable web vertical slice** accepts real dashcam videos, checks file integrity, extracts an actual frame using FFmpeg, optionally runs genuine AI models, and produces a preliminary PDF report.

> **Current limitations:** Not an official reporting service. No camera-to-mobile automatic sync, real-device-verified mobile release, Egyptian plate recognition, vehicle tracking, or traffic-violation verdict has been implemented. No fabricated detections are used. The operator-key login is for local development only.

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

The optional YOLO module runs **real vehicle detection from one extracted video frame**, not object tracking. Optional faster-whisper transcribes audio when available. You must supply/evaluate compatible model assets. Unconfigured/failed features are identified explicitly; the system never fabricates plate numbers, offenses or speech.

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
| Vehicle detection from one real frame | Implemented with optional user-supplied YOLO model; not benchmarked |
| Audio transcription | Implemented with optional faster-whisper model; not benchmarked |
| Plate OCR / vehicle tracking / automatic violations | Not implemented |
| Automatic DDPAI import to our app | Unverified; not implemented |
| Android / iPhone Expo source foundation | Implemented; real-device tests and production integration pending |
| Full multi-user security / production workflow | Not implemented |

Mobile source: [apps/mobile](apps/mobile/README.md). Read [system architecture](docs/ARCHITECTURE.md), [DDPAI feasibility](docs/CAMERA_FEASIBILITY.md), and [planned camera interface](integrations/dashcams/README.md).
