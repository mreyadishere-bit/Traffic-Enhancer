# Traffic Enhancer AI runtime

## Model chosen from the reference video

**Qwen2.5-VL-3B-Instruct** is the multimodal model. It analyzes **real time-stamped video frames**. Other specialized modules handle speech, object tracking, and plates.

The engine now contains executable integrations, but **GitHub CI does not download multi-GB weights or run Qwen on a GPU**. A real success claim requires running models against labelled, legally usable dashcam recordings. No generic multimodal model can verify traffic offenses by itself.

### Install

From project root with Python 3.11/3.12 and FFmpeg installed:

~~~bash
pip install -r requirements-vlm.txt
pip install -r requirements-ocr.txt
~~~

Install and evaluate appropriate weights for YOLO vehicle detection, Egyptian license plates, and local faster-whisper speech. Configure environment:

~~~bash
export TE_YOLO_MODEL="/path/to/vehicle_detector.pt"
export TE_ASR_MODEL="/path/to/local-whisper-model"
export TE_ENABLE_QWEN=1
export TE_QWEN_MODEL=Qwen/Qwen2.5-VL-3B-Instruct
# optional one-time Hugging Face download; disabled by default:
export TE_QWEN_ALLOW_DOWNLOAD=1
# only with suitable PLATE-SPECIFIC weights:
export TE_PLATE_MODEL="/path/to/egyptian-plate-detector.pt"
~~~

Use equivalent PowerShell syntax like \`$env:TE_ENABLE_QWEN="1"\` on Windows. For GPUs set \`TE_YOLO_DEVICE=cuda:0\` and compatible Whisper/CUDA settings. Do not activate all large models on a small CPU-only VPS; provision an isolated inference machine. Model weights and licenses must be independently verified for intended commercial use.

### Analysis contract

1. FFmpeg validates video, original hash and preview.
2. Faster-whisper produces an optional transcript from real audio.
3. Keyword parser identifies the driver's **unverified allegation** (English/Egyptian Arabic).
4. YOLO + BoT-SORT obtains object boxes and provisional IDs across sampled frames.
5. Qwen2.5-VL evaluates real timestamped frames, returning JSON scene summary and potential events requiring review (shoulder driving, red light, littering, missing plate).
6. Optional evaluated plate-detector + EasyOCR returns **unverified OCR candidates**.
7. No current system determines a spoken-about vehicle is a verified tracked car: it returns \`requires_review\`.
8. Candidate reconciler never sets a proven violation; the human must independently review.
9. PDF preserves statuses, filename, original SHA-256, hypotheses and limitations.

### Critical remaining work

Production authentication, resumable storage, a durable queued GPU worker, video-level benchmarks, official real-device integration, calibrated plate recognition, reliable vehicle color/make matching, incident rules with complete trajectories/signal states, cross-platform background constraints, privacy compliance and any authorized institutional integrations. A pretrained VLM is a helper for human review, not an official enforcement engine.

Sources:
- https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
- https://huggingface.co/docs/transformers/model_doc/qwen2_5_vl
- https://docs.ultralytics.com/modes/track/
