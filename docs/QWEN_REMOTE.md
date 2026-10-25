# Optional Qwen inference on a separate GPU service

This is an optional deployment mode. It runs the Traffic Enhancer API/web app on a small private server while **Qwen2.5-VL-3B-Instruct** runs on a separate, operator-controlled GPU endpoint.

Your own GPU inference host can use a Qwen-compatible vLLM OpenAI Chat Completions API. Qwen's official model card has instructions:
https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct

~~~bash
# On GPU machine, with appropriate model tooling and licensing:
vllm serve "Qwen/Qwen2.5-VL-3B-Instruct"
~~~

On the Traffic Enhancer machine, install the lightweight client:
~~~bash
pip install -r requirements-qwen-remote.txt
export TE_ENABLE_QWEN=1
export TE_QWEN_MODEL=Qwen/Qwen2.5-VL-3B-Instruct
export TE_QWEN_API_BASE=https://your-owned-gpu-service.example/v1
export TE_QWEN_API_KEY=your-secret
~~~

No external service is contacted by default. The remote adapter sends **video sample JPEG images** embedded as base64, including timestamps and the driver's unverified transcript, to the expressly configured service. It does **not** transmit the entire original video. **Road footage may contain personal and plate data**; use a secure authorized service with proper retention/deletion and privacy controls.

Plain HTTP is only permitted for loopback localhost/127.0.0.1; external endpoints require HTTPS. Do not expose a GPU endpoint directly without authentication or appropriate network controls. This feature is tested with a mocked compatible HTTP endpoint in CI; live remote Qwen inference still requires a real model server and representative evaluation.
