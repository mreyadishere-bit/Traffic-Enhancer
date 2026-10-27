# Free image-model failover and one-click vision-only retries

The OpenRouter Qwen model can return HTTP 404 even when a model page exists.
A 404 can indicate an unavailable free provider or an account routing/privacy
restriction. The app now tries its configured **free** image Qwen model first.
After an actual 404 it reads the public OpenRouter model catalog, requiring:
- Qwen model ID ending in ":free"
- image input modality and zero prompt/completion price

If a second usable Qwen model is listed, the app tries it. If unavailable,
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
