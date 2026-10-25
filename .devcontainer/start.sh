#!/usr/bin/env bash
set -euo pipefail
cd /workspaces/Traffic-Enhancer
if [ ! -s .codespace-api-key ]; then
  python -c 'import secrets;print(secrets.token_urlsafe(32))' > .codespace-api-key
  chmod 600 .codespace-api-key
fi
export TE_API_KEY="$(cat .codespace-api-key)"
export TE_ENV=development
if curl -fsS --connect-timeout 1 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
  echo "Traffic Enhancer is already running."
else
  nohup python -m uvicorn services.api.main:app --host 0.0.0.0 --port 8000 > /tmp/traffic-enhancer.log 2>&1 &
fi
echo "Open the PRIVATE forwarded port 8000 in Codespaces / Ports."
echo "Local operator key (keep private): $(cat .codespace-api-key)"
echo "Backend logs: tail -f /tmp/traffic-enhancer.log"
