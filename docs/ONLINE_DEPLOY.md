# Online demo: automatic deploy, no CMD

Traffic Enhancer can run in a **browser** on Render, without starting anything locally. The
demo uses a private operator key and a free OpenRouter Qwen2.5-VL remote model, if available.

**Important:** Render free machines have **512 MB RAM, 0.1 CPU, no persistent disk and auto-sleep**.
Files and the SQLite index are deleted when the service restarts/redeploys. This deployment
must be treated as a temporary *disposable demo*, never storage for evidence or personal data.
Never upload sensitive or identifying recordings without the necessary consent/authorization.

## One-time setup (all in browser)

1. Create a free Qwen API key at https://openrouter.ai/settings/keys .
2. Check whether `qwen/qwen-2.5-vl-7b-instruct:free` is still available at
   https://openrouter.ai/qwen/qwen-2.5-vl-7b-instruct:free (free models and quotas can change).
3. Create a free Render account at https://dashboard.render.com .
4. Connect Render to **your GitHub** account (this is required for automatic deploys).
5. Open https://dashboard.render.com/select-repo?type=blueprint or choose **New → Blueprint**.
   Select `mreyadishere-bit/Traffic-Enhancer` and use its root `render.yaml`. Or open the [one-click deploy link](https://render.com/deploy?repo=https://github.com/mreyadishere-bit/Traffic-Enhancer).
   The configured branch is `main`; merge the tested feature PR first.
6. When Render requests `TE_QWEN_API_KEY`, paste your OpenRouter key into the **Render
   secret form only**. Do not commit the key, put it into HTML, or share it in chat.
7. Let the deployment finish. Open the generated `https://<your-service>.onrender.com`
   address listed on your Render dashboard. This document intentionally does not invent a
   deployment URL. Read the generated `TE_API_KEY` from Render service → Environment,
   and paste it into the operator login form.
8. Set **Auto-Deploy: After CI Checks Pass** in Render settings if not already selected.
   Afterwards every successful commit/merge to `main` automatically updates the site
   without PowerShell or CMD. Failed checks prevent deployment.

The `render.yaml` blueprint sets `TE_QWEN_API_BASE=https://openrouter.ai/api/v1`,
`TE_ENABLE_QWEN=1` and selects the free 7B visual model. Remote AI must be online; there
is no guaranteed free, always-on GPU. YOLO and local Whisper are intentionally NOT
loaded on this low-memory demo instance. For audio, give a written driver description.

### Actual production requirements

For genuine use with road evidence and third-party footage:
- Paid service or independent server + durable encrypted object storage and database.
- Real user authentication, individual permissions, deletion policy and audit trails.
- Queued/isolated processing workers, rate limits, resource and network protections.
- Camera vendor integration and evaluation on real Egyptian road data.
- Real GPU or paid inference with privacy/retention terms appropriate to recordings.
- Do not use sample frame commentary as a legally verified traffic offense.

An existing VPS may be suitable for lightweight web hosting, but do **not** modify
Caddy, Supabase, ports 80/443 or other services without an authorized separate
deployment plan. The blueprint deploys outside the existing VPS.

## Optional cloud speech recognition

If the recording includes real audio, the cloud demo can use Groq-hosted Whisper.
Create an API key at https://console.groq.com/keys and add it to Render **Environment**
as `TE_GROQ_API_KEY`. The Blueprint sets `TE_GROQ_ASR_MODEL=whisper-large-v3-turbo`.
Your selected clip audio will be sent to Groq after explicit operator configuration.
The Groq free tier has file-size and request limits (see their documentation), and
not every recording produces an intelligible transcript. Do not send third-party
audio without authorization.

If no key is configured, the speech stage is displayed as not configured and
the operator can manually enter a driver statement, explicitly labeled as a claim.

## What counts as successfully deployed?

The Render service must show **Live**, the health endpoint must return 200, the operator
key must authorize API calls, a short nonsensitive test clip must upload/process,
the Qwen stage must return a genuine `completed` result (not `not_configured`),
and the PDF must export. Until this happens, code/CI completion does not imply a
running internet-accessible production system.
