# Run Traffic Enhancer through GitHub only (no CMD, no Blitz)

A **private GitHub Codespaces demo** runs the original app in a browser.
It is not a permanent 24/7 site. Personal GitHub accounts have a limited
free monthly Codespaces compute/storage allowance.

## 1. Save two new API keys in GitHub Codespaces secrets

Because the previous keys were shown in a screenshot, revoke them and create
new ones. Do **not** paste them into the repository or chat.

Open https://github.com/mreyadishere-bit/Traffic-Enhancer/settings/secrets/codespaces

Select **New repository secret**, and create:

- \`TE_QWEN_API_KEY\` — create at https://openrouter.ai/settings/keys
- \`TE_GROQ_API_KEY\` — create at https://console.groq.com/keys
- \`TE_API_KEY\` (optional) — a strong operator password you choose yourself.
  Without it, a random key is saved in \`.codespace-api-key\` in Codespaces,
  which you can open by clicking the file in the Codespaces Explorer.

These are **Codespaces** secrets, not Actions secrets. Github injects them
when the Codespace starts. Stop/restart an existing Codespace after changing
the secrets to load the new values.

## 2. Open Traffic Enhancer without any commands

**[Launch in GitHub Codespaces](https://codespaces.new/mreyadishere-bit/Traffic-Enhancer?quickstart=1)**

Choose branch \`main\` and create a codespace. Dependencies and FFmpeg install
automatically, then the app starts and forwards port **8000** privately.

If a browser window does not appear automatically, click the **Ports** tab and
open port **8000** from there. On the sign-in page use your \`TE_API_KEY\`.
If you did not create that optional secret, click \`.codespace-api-key\` in
Codespaces Explorer, copy its value, and enter it in the login form.

GitHub Codespaces defaults to port **PRIVATE**; do not change it to public.

When the new Codespaces secrets exist:
- Qwen2.5-VL uses \`qwen/qwen-2.5-vl-7b-instruct:free\` via OpenRouter for a few sampled video frames.
- Groq uses \`whisper-large-v3-turbo\` for video audio.
- Both free endpoints have availability/usage limits and can return errors.
- The app does not automatically enable GPU-dependent YOLO/plate detection.

## After GitHub code updates

The web/API automatically reloads after edits inside the Codespace.
On restart, an unchanged \`main\` checkout automatically fast-forwards from
GitHub. If there are uncommitted edits, changes are preserved instead.
You can stop/restart via https://github.com/codespaces without running CMD.

GitHub Pages cannot run the Python/FFmpeg backend, and Codespaces is not
always-on production hosting. Do not process sensitive or identifying footage
until the operator access and data protections are improved.
