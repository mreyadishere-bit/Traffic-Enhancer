# Start Traffic Enhancer directly from GitHub

## Option A — open in GitHub Codespaces (browser)

[Create a private Codespace](https://codespaces.new/mreyadishere-bit/Traffic-Enhancer?quickstart=1)

GitHub builds a Python environment, installs core dependencies and runs the FastAPI web app on port 8000. The forwarded port is configured **PRIVATE**. Open the "Ports" tab, then the URL for port 8000. In the Codespace terminal, get the generated operator key:

~~~bash
cat .codespace-api-key
~~~

It is saved inside that Codespace only. Do not publish your code-space port or share the operator key. The repository's GitHub Actions run checks whenever you push to main. An existing Codespace may need git pull and container rebuild after updates.

**Limits:** Codespaces isn't a permanent public hosting solution; it can stop while inactive, may have usage costs, and generally doesn't provide a GPU suitable for Qwen2.5-VL. Do not upload sensitive third-party recordings to a Codespace without appropriate authorization and data protection.

## Option B — Windows double-click launcher (recommended for PC)

From an existing clone, run \`git pull --ff-only origin main\`. Then double-click:

- \`Start-Traffic-Enhancer.cmd\`: lightweight local evidence studio.
- \`Start-Traffic-Enhancer-AI.cmd\`: additionally installs YOLO + Whisper packages and configures their optional models. First analysis can download model weights.

The launcher creates the Python virtual environment (Python 3.12 required), installs dependencies, generates a random operator key, starts the backend and opens the browser. The private operator key is also in \`.traffic-local-key\` (Git-ignored). It never deploys or touches other host services.

GitHub Actions automatically packages a downloadable Windows ZIP on every push. Find it under **Actions → Package Windows launcher → latest successful run → Artifacts**. Unzip before double-clicking.

## Option C — permanent public deployment

This requires a separate authorized hosting provider / GPU inference machine, environment secrets, identity & role-based access, secured storage and a deployment target. **GitHub Pages alone cannot execute FastAPI, Python AI models or store uploaded evidence.** The project does not pretend that uploading to GitHub means an internet-facing production service exists.

Keep all Codespaces forwarded ports private. Don't use this development operator-key endpoint for public access.
