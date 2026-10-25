# Architecture / first vertical slice

## What works in this commit

Web browser (in-memory development operator key) → authenticated FastAPI upload → streamed original video → SHA-256 integrity hash and FFprobe validation → SQLite metadata → in-process processing task → actual FFmpeg keyframe → optional real one-frame YOLO object detection and/or faster-whisper transcript → stored structured result → private operator playback and preliminary English PDF report.

Do not assume the dashcam is automatically connected. This path starts **after a file has been imported to the browser**.

## Code ownership

- \`web/\`: responsive evidence workspace and authenticated evidence interactions.
- \`services/api/main.py\`: API, authentication, input limits, evidence storage, processing state and retrieval.
- \`services/api/analysis.py\`: FFmpeg-derived frame, real optional AI model execution.
- \`services/api/report.py\`: downloadable preliminary PDF with limitations.
- \`tests/\`: real generated-video API integration tests.
- \`integrations/dashcams/\`: adapter requirements, not a vendor implementation.

## Honest limitations and risk controls

This is a **single-operator development MVP**, not a production-safe environment. In-process background tasks can be lost on restart. Local SQLite and file storage need upgrades for multi-user use. The operator key is shared and unscoped; media cannot be exposed across untrusted users. Video timestamps in the current report are *upload times*, not proven capture times. SHA-256 proves the uploaded copy hasn't changed, not the provenance or authenticity of the original recording. FFmpeg reads untrusted videos, so a public service requires sandboxed workers, process limits and scanning.

Prior to external deployment: proper user identities, per-user RBAC / object permissions, TLS, signed URLs, upload quotas, media sandboxing, storage encryption, long-lived resumable uploads, durable job queue, audit trail, user deletion/retention policy, detailed legal and privacy assessment for Egypt, and empirical human-reviewed model accuracy. A violation classifier must **not** auto-issue citations.

## Next technical milestones

1. Strong authentication, access control, immutable S3-compatible evidence store.
2. Durable processing jobs with retries and idempotent uploads.
3. Sampled-frame object detection with tracking and evaluated Egyptian plate OCR.
4. Grounded incident classification with uncertainty and authorized reviewer tools.
5. React Native Android/iOS apps with import/share workflows; physical-device tests.
6. Direct dashcam adapter only after vendor-confirmed SDK/API or tested supported connection method.

The planned monorepo can grow into apps/web, apps/mobile, services/api, services/ai-worker, integrations/dashcams, packages/contracts and infrastructure without discarding working modules.
