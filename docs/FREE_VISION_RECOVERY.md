# Free image-model failover and one-click vision-only retries

The OpenRouter Qwen model can return HTTP 404 even when a model page exists.
A 404 can indicate an unavailable free provider or an account routing/privacy
restriction. The app now tries its configured **free** image Qwen model first.
After an actual 404 it reads the public OpenRouter model catalog, requiring:
- A model ID ending in ":free" (prefer Qwen when available)
- Image input modality and zero prompt/completion/image/request prices

If another eligible Qwen model is listed, the app prefers it. Otherwise it
can try a catalog-verified no-cost image model from another provider, before
it can try documented \`openrouter/free\`, which selects a **free vision model**
automatically. That final provider may be **NOT Qwen**. Evidence Studio
records/displays the actual model ID returned by the inference response.
No paid model is ever silently selected. HTTP 401/402/403/429 stop immediately;
no retry is made to bypass an account/billing/rate limit.

For existing cases with only visual-analysis failure, go to **New analysis**
or **Evidence studio**, select the saved case, then click:

**Retry visual AI only · keep YOLO and full video**

This calls \`POST /api/v1/incidents/{id}/retry-vision\`. The backend refreshes
only visual_reasoning and violation_assessment in SQLite, preserving all
other analysis records and the previously produced full-length video.
No original upload, YOLO, tracking, speech transcription, OCR or rendering
is repeated. You must still have a usable OpenRouter API key in Streamlit
Secrets. Public free tiers can be throttled or blocked by routing restrictions.

In System health, check the currently listed free Qwen image models without
sending any audio or video. The public model list is not a proof the provider
accepts your account's inference requests. A successful vision report is
preliminary and requires human review, not an automatic citation.


## CPU evidence first — remote vision second

The latest analysis sequence renders the full selected YOLO-annotated MP4
and attempts plate OCR **before** waiting on optional OpenRouter vision.
The video may appear while the final visual stage is still running.
This does not turn pixel-plane motion into physical speed or validate OCR.

When a case is PROCESSING, old saved model errors shown in the viewer are
historical; they do not prove the current attempt failed. Free image requests
have bounded per-operation timeouts (read: 70 seconds, connect: 8 seconds) and
at most three attempts (configured free model, one catalog alternate, free router).
If routing is still blocked, check the live synthetic-image key test in System
Health, then review https://openrouter.ai/settings/privacy. Do not assume
account settings can be changed automatically by Traffic Enhancer.


## HTTP 200 but no actual model answer (October 27, 2026)

Some OpenRouter multimodal free-model requests return HTTP 200 but
`choices[0].message.content` is absent, null, or a list of content blocks.
Older builds raised a generic `ValueError: model request failed`. The new
normalizer handles text-block arrays and classifies empty completion,
reasoning-only output, exhausted output tokens, model refusal, embedded provider
errors, and invalid JSON separately **without exposing provider response bodies
or credentials**.

The optional OpenRouter routing logic retries an *empty* HTTP 200 final answer
using only a catalog-verified zero-cost vision model or the free router, with at
most three model calls and no retries on HTTP 401/402/403/429 or an embedded
provider-declared error. It raises the output budget from 450 to 900 tokens.
Extra free inference requests can consume the account's rate-limited quota.
Even successful model text must parse as the expected scene JSON, otherwise
the outcome is marked unparseable, not as a verified violation.

Run **System health → Test my API key with a generated image** to verify the
key accepts image inference with actual text output. For existing saved videos,
choose **Evidence studio → Retry visual AI only · keep YOLO and full video**.
Do not rerun all stages unless the original YOLO artifacts themselves failed.
A free-provider/account routing issue can still prevent remote AI entirely.

Plate OCR remains tentative: the small night-time plate regions in source
footage cannot reliably be turned into exact Egyptian registration characters
without sufficient actual image resolution. Never invent characters.
