"""Re-running visual analysis must preserve all saved YOLO/MP4 facts."""
import json
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from services.api import main,qwen


def test_retry_vision_preserves_previous_analysis_and_evidence(tmp_path,monkeypatch):
    monkeypatch.setattr(main,"DATA",tmp_path)
    monkeypatch.setattr(main,"DB",tmp_path/"db.sqlite")
    monkeypatch.setattr(main,"EVIDENCE",tmp_path/"evidence")
    monkeypatch.setattr(main,"DERIVED",tmp_path/"derived")
    monkeypatch.setattr(main,"KEY","ci-private-key")
    before={"vehicle_detection":{"status":"completed","detections":[{"label":"car"}]},
            "object_tracking":{"status":"completed","tracks":[{"track_id":1}]},
            "transcription":{"status":"completed","text":"Take photo"},
            "plate_recognition":{"status":"completed","value":None},
            "driver_claim":{"verbatim":"Take photo"},
            "full_length_video":{"status":"completed","duration_seconds":29.5},
            "visual_reasoning":{"status":"failed","note":"OpenRouter 404"},
            "violation_assessment":{"status":"unavailable"}}
    with TestClient(main.app) as client:
        case_id="b"*32
        with main.connect() as db:
            db.execute("""INSERT INTO incidents
                (id, filename, created_at, sha256, bytes, duration, video_json, status, analysis_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (case_id,"video.mp4",datetime.now(timezone.utc).isoformat(),
                 "a"*64,50,29.5,json.dumps({"duration_seconds":29.5}),
                 "ready",json.dumps(before)))
        created=main.DERIVED/(case_id+".tracked.mp4")
        created.write_bytes(b"unchanged-mp4-artifact")
        calls=[]
        def inference(video,duration,claim):
            calls.append((duration,claim))
            return {"status":"completed","model":"qwen/free-vl:free",
                    "observations":{"potential_events":[],
                                    "scene_summary":"Vehicles visible"}}
        monkeypatch.setattr(qwen,"describe_video",inference)
        response=client.post(f"/api/v1/incidents/{case_id}/retry-vision",
                             headers={"Authorization":"Bearer ci-private-key"})
        assert response.status_code==200,response.text
        assert response.json()["vision_status"]=="completed"
        data=client.get(f"/api/v1/incidents/{case_id}",
                        headers={"Authorization":"Bearer ci-private-key"}).json()
        after=data["analysis"]
        assert after["vehicle_detection"]==before["vehicle_detection"]
        assert after["object_tracking"]==before["object_tracking"]
        assert after["full_length_video"]==before["full_length_video"]
        assert after["transcription"]==before["transcription"]
        assert after["visual_reasoning"]["status"]=="completed"
        assert data["status"]=="ready"
        assert created.read_bytes()==b"unchanged-mp4-artifact"
        assert len(calls)==1
