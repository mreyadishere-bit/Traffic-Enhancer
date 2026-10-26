# Traffic Enhancer — Streamlit Community Cloud

This repo now includes a **native Streamlit browser UI** that invokes the existing
FastAPI/FFmpeg analysis pipeline without running a separate publicly exposed API.

### Deploy once (all from your browser; no CMD, no credit card)

1. Make sure this feature has passed tests and been merged into \`main\`.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in using GitHub.
3. Click **Create app → Yup, I have an app**.
4. Select:
   - **Repository:** \`mreyadishere-bit/Traffic-Enhancer\`
   - **Branch:** \`main\`
   - **Main file path:** \`streamlit_app.py\`
   - **App URL:** choose an available subdomain, e.g. \`traffic-enhancer-lab\`.
5. In **Advanced settings → Secrets**, paste TOML values like:

~~~toml
TE_API_KEY = "REPLACE_WITH_NEW_LONG_RANDOM_PRIVATE_PASSWORD"
TE_QWEN_API_KEY = "REPLACE_WITH_NEW_OPENROUTER_KEY"
TE_QWEN_API_BASE = "https://openrouter.ai/api/v1"
TE_QWEN_MODEL = "qwen/qwen-2.5-vl-7b-instruct:free"
TE_QWEN_FRAMES = "2"
TE_GROQ_API_KEY = "REPLACE_WITH_NEW_GROQ_KEY"
TE_GROQ_ASR_MODEL = "whisper-large-v3-turbo"
~~~

All values above are **examples, not usable secrets**. Create fresh keys:
[OpenRouter keys](https://openrouter.ai/settings/keys) and
[Groq keys](https://console.groq.com/keys). Keys previously shared in chat
screenshots must be revoked. Your Streamlit operator password is unrelated
to either provider's API key, and must be at least 16 characters.
You can omit the Groq or OpenRouter credentials to disable that stage.
Never commit \`.streamlit/secrets.toml\` or put secrets in frontend code.

6. Click **Deploy**, then visit the **actual URL Streamlit gives you**.
   Sign into the app with the private \`TE_API_KEY\` from your Streamlit secrets.

### Updates without manual deployment

Every change merged or pushed to the configured \`main\` branch gets picked up
and redeployed automatically by Streamlit Cloud. You do not need PowerShell,
Windows, GitHub Codespaces, Render, Blitz or a manually running FastAPI port.

### Real capabilities and important limitations

- Preserves the existing FastAPI workflow and PDF export, and shows actual
  model state/error messages instead of fake analysis results.
- Uses remote Qwen2.5-VL vision and optional remote Whisper via configured keys.
  **YOLO and Egyptian plate OCR are deliberately disabled in this free cloud
  entrypoint.** To run those, you need a sufficiently sized separate worker.
- Streamlit Community Cloud memory/CPU are limited and resources aren't a
  permanent file/database vault. The app can go to sleep or restart at any
  time, wiping local SQLite/video files. **Do not upload sensitive third-party
  footage or rely on this deployment for evidence preservation.**
- Video uploads are capped at 70 MB by the app; select at most 180 seconds.
  The entire uploaded source still crosses the network; slower connections
  may need a smaller source copy.
- One shared password protects the dashboard; this is not secure multi-user
  authentication, case access policies, durable processing queues, or legal
  traffic enforcement.
- No official plate registry or government traffic system is connected.
  Suggested events are unverified.

When production requirements matter, use a dedicated deployment with secure
storage/authentication and a GPU worker. The original local FastAPI app
continues to function unchanged.

Documentation: https://docs.streamlit.io/deploy/streamlit-community-cloud/
