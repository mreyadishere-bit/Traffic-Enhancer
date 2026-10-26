#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
# Safely fast-forward clean main checkouts whenever the Codespace resumes.
if [ "$(git branch --show-current 2>/dev/null || true)" = "main" ] &&
   git diff --quiet && git diff --cached --quiet; then
  timeout 20 git pull --ff-only origin main >/dev/null 2>&1 ||
    echo "GitHub sync skipped; no local files were overwritten."
fi
# Codespaces secrets are environment variables. Never print/write provider keys.
if [ -z "$TE_API_KEY" ]; then
  if [ ! -s .codespace-api-key ]; then
    python -c 'import secrets;print(secrets.token_urlsafe(32))' > .codespace-api-key
    chmod 600 .codespace-api-key
  fi
  export TE_API_KEY="$(cat .codespace-api-key)"
  echo "Login: use the .codespace-api-key file (click in Explorer)."
else
  echo "Login: use the TE_API_KEY you saved under GitHub Codespaces secrets."
fi
export TE_ENV=development
if [ -z "$TE_DATA_DIR" ]; then export TE_DATA_DIR="$(pwd)/data"; fi
if [ -n "$TE_QWEN_API_KEY" ]; then
  export TE_ENABLE_QWEN=1
  if [ -z "$TE_QWEN_API_BASE" ]; then export TE_QWEN_API_BASE="https://openrouter.ai/api/v1"; fi
  if [ -z "$TE_QWEN_MODEL" ]; then export TE_QWEN_MODEL="qwen/qwen-2.5-vl-7b-instruct:free"; fi
  if [ -z "$TE_QWEN_FRAMES" ]; then export TE_QWEN_FRAMES=2; fi
  echo "Qwen remote vision enabled (operator-supplied Codespaces secret)."
else
  export TE_ENABLE_QWEN=0
  echo "Qwen remote vision disabled; add TE_QWEN_API_KEY in GitHub Codespaces secrets."
fi
if [ -n "$TE_GROQ_API_KEY" ]; then
  if [ -z "$TE_GROQ_ASR_MODEL" ]; then export TE_GROQ_ASR_MODEL=whisper-large-v3-turbo; fi
  echo "Groq Whisper remote speech enabled (operator-supplied Codespaces secret)."
else
  unset TE_GROQ_ASR_MODEL || true
  echo "Groq speech disabled; add TE_GROQ_API_KEY in GitHub Codespaces secrets."
fi
export TE_ASR_ALLOW_DOWNLOAD=0
if curl -fsS --connect-timeout 2 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
  echo "Traffic Enhancer already running at private forwarded port 8000."
else
  nohup python -m uvicorn services.api.main:app \
    --host 0.0.0.0 --port 8000 --reload \
    --reload-dir services --reload-dir web \
    > /tmp/traffic-enhancer.log 2>&1 < /dev/null &
  echo "Traffic Enhancer auto-started. Open private forwarded port 8000."
fi
echo "No CMD or manual startup command is required."
