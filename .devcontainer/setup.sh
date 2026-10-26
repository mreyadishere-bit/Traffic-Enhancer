#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "Preparing Traffic Enhancer in GitHub Codespaces..."
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg
fi
python -m pip install --disable-pip-version-check -r requirements.txt
echo "Dependencies ready. GPU models are NOT downloaded on this Codespace."
