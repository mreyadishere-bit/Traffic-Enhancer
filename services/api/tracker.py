"""Video vehicle tracking using an actual Ultralytics model + BoT-SORT.

When model weights aren't configured, never return synthetic detections/IDs.
Track IDs are local to ONE video, and can switch after occlusion.
"""
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def cached_vehicle_model(weights):
    from ultralytics import YOLO
    return YOLO(weights)


VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "motorbike"}


def track_vehicles(video, video_metadata: dict) -> dict:
    weights = os.getenv("TE_YOLO_MODEL", "").strip()
    if not weights:
        return {"status": "not_configured", "model": None, "tracks": [],
                "detections": [], "note": "Set TE_YOLO_MODEL for actual video tracking."}
    try:
        model = cached_vehicle_model(weights)
        max_frames = min(180, max(1, int(os.getenv("TE_TRACK_MAX_FRAMES", "90"))))
        stride = min(30, max(1, int(os.getenv("TE_TRACK_STRIDE", "5"))))
        fps = float(video_metadata.get("frame_rate") or 0)
        detections, tracks = [], {}
        # Stream outputs avoid loading the entire video into RAM. Each input
        # belongs to the SAME recording: IDs persist through the track call.
        stream = model.track(source=str(video), stream=True, tracker="botsort.yaml",
                             conf=0.25, vid_stride=stride,
                             device=os.getenv("TE_YOLO_DEVICE", "cpu"), verbose=False)
        count = 0
        for frame in stream:
            if count >= max_frames:
                break
            at = round(count * stride / fps, 2) if fps > 0 else None
            count += 1
            boxes = frame.boxes
            if boxes is None:
                continue
            ids = boxes.id.tolist() if boxes.id is not None else [None] * len(boxes)
            for idx, obj in enumerate(boxes):
                label = str(frame.names[int(obj.cls[0])])
                if label not in VEHICLE_CLASSES:
                    continue
                bbox = [round(float(v), 1) for v in obj.xyxy[0].tolist()]
                confidence = round(float(obj.conf[0]), 4)
                object_id = int(ids[idx]) if ids[idx] is not None else None
                item = {"frame_index": count - 1, "second": at, "label": label,
                        "confidence": confidence, "box_xyxy": bbox, "track_id": object_id}
                if len(detections) < 250:
                    detections.append(item)
                if object_id is not None:
                    current = tracks.setdefault(object_id, {"track_id": object_id,
                        "label": label, "observations": [], "color": None, "make": None})
                    if len(current["observations"]) < 120:
                        current["observations"].append({
                            "second": at, "box_xyxy": bbox, "confidence": confidence})
        return {"status": "completed", "model": weights, "method": "BoT-SORT",
                "tracks": list(tracks.values())[:80], "detections": detections,
                "sampled_frames": count, "stride": stride,
                "note": "Sampled-frame detection/tracking; IDs can switch; vehicle color/make not classified."}
    except Exception as exc:
        return {"status": "failed", "tracks": [], "detections": [], "model": weights,
                "note": f"{type(exc).__name__}: {str(exc)[:220]}"}
