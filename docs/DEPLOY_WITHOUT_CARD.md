# Traffic Enhancer: deployment without a credit card

**Recommended no-card demonstration host:** [blitz.cloud](https://dashboard.blitz.cloud/), as documented in their [GitHub deployment instructions](https://blitz.cloud/docs/deploy-from-github/). Their free plan currently includes GitHub auto-deploy, HTTPS, an app subdomain, 512 MB shared RAM and 10 GB storage. Apps sleep after 30 minutes of inactivity. Verify the account's eligibility and limits in the dashboard. This is NOT an evidence-grade production hosting plan.

## From the browser — no CMD or terminal

1. Open https://dashboard.blitz.cloud/ and register with GitHub or email. Confirm the email address. Do not add a credit/debit card.
2. Choose **Host something new → My own code** and connect GitHub, giving access to `mreyadishere-bit/Traffic-Enhancer` only. Paste the GitHub URL if requested.
3. Select the **main** branch only after the Evidence Studio v2 PR has passed end-to-end tests and been merged. To preview an experimental branch, choose `feature/evidence-studio-v2` under Advanced, and do not treat it as production.
4. Pick the root **Dockerfile**, which declares **EXPOSE 8000** and starts the FastAPI app on port **8000**. The platform detects the declared port. Do not choose the mobile app as the deployment target.
5. On the app's **Environment** tab set the following private environment variables:

   | Name | Value |
   | ---- | ----- |
   | `TE_ENV` | `production` |
   | `TE_API_KEY` | A long **random private** value. Never reuse `dev-only-change-me`. |
   | `TE_ENABLE_QWEN` | `1` |
   | `TE_QWEN_API_BASE` | `https://openrouter.ai/api/v1` |
   | `TE_QWEN_MODEL` | `qwen/qwen-2.5-vl-7b-instruct:free` **only if currently available** |
   | `TE_QWEN_API_KEY` | OpenRouter API key from https://openrouter.ai/settings/keys |
   | `TE_GROQ_ASR_MODEL` | `whisper-large-v3-turbo` (optional) |
   | `TE_GROQ_API_KEY` | Groq key from https://console.groq.com/keys (optional) |
   | `TE_MAX_SOURCE_MB` | `30` |
   | `TE_MAX_UPLOAD_MB` | `25` |
   | `TE_DATA_DIR` | `/app/data` |

6. Under **Advanced settings → Kept folders** (or later **Settings → Files**), ensure `/app/data` is kept. The Dockerfile declares `VOLUME ["/app/data"]`. On the free plan these files can survive routine container restarts but **are not automatically backed up**: export anything important yourself. Restart the service after saving environment variables. Open the **real HTTPS URL shown by the dashboard** and enter your private `TE_API_KEY` in the login form. The app only has a shared operator key; restrict access to authorized testers and do not upload private road footage.
7. Once GitHub is connected, blitz.cloud builds new versions automatically on branch pushes. Free-plan builds may be delayed/throttled; see [the platform's published deploy cadence](https://blitz.cloud/docs/deploy-from-github/#when-your-code-changes).

## Realistic limitations

- The free instance has limited RAM and CPU. Local YOLO/Whisper model inference, large video re-encoding, and Qwen local GPU inference are **not guaranteed to work**. Use remote Qwen and optional remote speech to demonstrate analysis steps, or prefer your existing VPS with an isolated deployment when locally hosted FFmpeg work is required.
- Free OpenRouter model availability and inference rate limits can change. Using a key doesn't guarantee that Qwen produces valid or correct traffic-violation interpretations.
- The current service uses SQLite and local evidence files. Do not assume persistent, encrypted, access-controlled evidence storage, or per-user authorization. A demo URL is not a verified traffic enforcement service.
- The existing OVH VPS can be used **without any new hosting account or credit card**, but safe deployment requires a separately isolated container + secure ingress (for example, Cloudflare Tunnel with a domain) and appropriate authentication. Do not alter existing Caddy, Supabase, WhatsApp or ports 80/443 without an explicit deployment plan.
- **Do not publish API keys in GitHub files, pull requests, screenshots, or chat**. Set them only in the provider's encrypted environment secrets.

## Acceptance checks

The service must show Running; `/api/v1/health` must be healthy; the operator login must work; a nonsensitive short clip must upload; the report must export; and the relevant AI stages must return real supported results. Until these checks pass on the actual hosted URL, no public deployment is confirmed.
