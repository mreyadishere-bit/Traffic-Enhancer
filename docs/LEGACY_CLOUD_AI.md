# Legacy Traffic Enhancer (original interface): cloud AI settings

This branch preserves the **original v0.1 interface** while adding support for
real remote Qwen2.5-VL vision and Groq Whisper transcription. Both features
must be explicitly enabled by the operator. Secrets are **never saved in GitHub**.

Set these environment variables under **blitz.cloud → Apps → Traffic Enhancer → Environment**:

| Environment variable | Value |
| --- | --- |
| `TE_API_KEY` | Generate a new long private random key in blitz.cloud |
| `TE_ENV` | `production` |
| `TE_ENABLE_QWEN` | `1` |
| `TE_QWEN_API_BASE` | `https://openrouter.ai/api/v1` |
| `TE_QWEN_MODEL` | `qwen/qwen-2.5-vl-7b-instruct:free` (availability varies) |
| `TE_QWEN_API_KEY` | New key from https://openrouter.ai/settings/keys |
| `TE_QWEN_FRAMES` | `2` for a CPU-limited demo (less temporal context) |
| `TE_GROQ_ASR_MODEL` | `whisper-large-v3-turbo` |
| `TE_GROQ_API_KEY` | New key from https://console.groq.com/keys |
| `TE_ASR_ALLOW_DOWNLOAD` | `0` |
| `TE_YOLO_MODEL` | **Leave empty** on small cloud hosting |
| `TE_PLATE_MODEL` | **Leave empty** unless validated Egyptian weights available |

After saving env vars, rebuild/restart the app using the **new commit on main**.
Do not enter a key through the frontend, commit keys to GitHub, or paste
key values into support chats. Credentials previously shared through a screenshot
should be **revoked and replaced**.

The app's `AI Studio` shows whether the vision and speech stages have
completed on an actual uploaded sample, but the word `completed` means
execution finished; it does not validate the correctness of the traffic
findings. Without a GPU, only the remote stages are reasonable for testing.
There is no official traffic violation verification and no production
per-user authentication on this legacy interface.

**Important:** free-tier services have variable quotas, latency and
model availability. Do not upload sensitive footage without the consent and
privacy protections required by your jurisdiction.
