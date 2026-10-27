# Understand the OpenRouter free vision diagnostic

The previous Streamlit System Health button searched **only Qwen image models**
and collapsed a real catalog GET failure into the same "none found" message.

This was misleading. System Health now separates:
1. Public catalog connectivity for models accepting image input with $0
   prompt/completion/image/request costs.
2. Free Qwen image models versus other free image models, with actual IDs.
3. Optional authenticated /models/user listing, filtered by account/provider
   privacy restrictions. A 403 here may mean the key lacks management
   permissions; do not claim the actual inference is blocked from this alone.
4. An **explicit opt-in**, one-request free-router inference check using a
   synthetic 40x40 PNG, NOT uploaded road footage.

A model listed publicly is **not proof** it works for the Streamlit key.
The real probe returns the actual model chosen by openrouter/free, or HTTP
401 (invalid key), 402, 403, 404 (routing/no compatible provider), or 429.
Neither keys, OpenRouter response bodies nor road video are displayed by
these checks. No priced fallback is used.

Official documentation:
- https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties
- https://openrouter.ai/docs/api/api-reference/models/list-models-filtered-by-user-provider-preferences-privacy-settings-and-guardrails
- https://openrouter.ai/openrouter/free

System Health also includes an optional **CPU YOLO + plate locator + Arabic
Tesseract runtime self-test**. It uses only a generated blank image. It invokes
the actual ONNX runtime and may download public detector weights on first use.
"Ready" means the model loaded and executed, **not** that it detects vehicles,
reads Egyptian registrations or measures speed accurately on road footage.
Failures expose exception types only (not secret values or upload content).
The health page shows a fixed UI revision label to help detect stale deployments.

For existing cases whose visual stage failed, open Evidence Studio and click
Retry visual AI only. This reuses the previously uploaded clip if it still
exists, preserving YOLO and annotated video. A failed public catalog is not
fixed by inventing a fake plate/traffic-violation classification.
