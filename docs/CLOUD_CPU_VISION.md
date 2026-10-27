# CPU YOLO + Egyptian license plate AI on Streamlit Community Cloud

The public Streamlit demo now **attempts genuine local CPU inference**. No
paid API is needed for the **vehicle detector or plate detector**.

## Actual models and processing

1. Vehicle detection: pretrained YOLOv8n COCO ONNX, CPU via onnxruntime.
   Public model: https://huggingface.co/unileon-robotics/YOLO8-ONNX
   Classes included: car, truck, bus, motorcycle.
2. Egyptian plate detection: custom YOLOv8n ONNX trained for Egyptian license
   plates (model card reports validation figures; not independently reproduced).
   Public model: https://huggingface.co/omasayeddd/egyptian-license-plate-detector
3. OCR: Debian Tesseract Arabic + English on *actual detected plate crops*.
   It can return no characters when blurred or tiny. Text is a **candidate**,
   never automatically the verified license plate.
4. Files are sampled in **5 frames per model per case**. Outputs retain
   original frame timestamps and pixel bounding boxes. Association of
   detections across samples uses rudimentary IoU, **not BoT-SORT**. Do not
   claim continuously tracked or reliably identified vehicles.
5. Qwen vision and Groq speech remain separately optional remote providers.
   Adding CPU models does NOT fix provider 401 errors.

## Performance limits

First processing downloads the two pretrained ONNX models from Hugging Face
into an ephemeral cache folder; cloud restarts may re-download weights. No
weights are committed to GitHub. Each model uses one CPU thread to reduce
overload. On a small Community Cloud instance, downloads/FFmpeg/inference
may be slow or hit resource limits. The 5 sample frames cannot establish
temporal violations (red light, shoulder, littering). See:
https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app

Streamlit installs \`onnxruntime\` from \`requirements.txt\`; \`packages.txt\`
installs \`tesseract-ocr\` and \`tesseract-ocr-ara\`. GitHub auto-deployment
will rebuild the Python/apt environments.

To disable this feature if the free instance cannot support it, add
\`TE_CLOUD_VISION = "0"\` in Streamlit app secrets, then reboot. Existing
Windows Ultralytics + BoT-SORT and EasyOCR pipeline remains unchanged.

## Limits of the result

- COCO object detection is not proof of vehicle make/model, color, identity,
  registration, ownership, or a traffic offense.
- Egyptian OCR output depends on plate pixels visible in original video.
  Wide night-time traffic CCTV can be too low resolution to read any plate.
- This is a public no-login **demo**. Do not upload identifying or private
  road recordings without authorization. Files are not secure permanent
  evidence storage and processing limits can be exhausted anonymously.
- Model licenses must be reviewed before redistribution/commercial use:
  YOLOv8 from Ultralytics is AGPL-3.0, while the Egyptian plate model's
  repository declares MIT. The underlying architectures and weights may
  have separate obligations.
- Test coverage verifies model decoding and integration logic with synthetic
  tensors and unit fixtures, NOT field accuracy; evaluate on representative
  consented Egyptian footage before real deployment.
