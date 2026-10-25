"""Evidence-aware, non-enforcement reconciliation of voice and visual model."""
SUPPORTED = {"shoulder_driving", "red_light", "littering", "missing_plate"}


def match_target(claim: dict, tracking: dict) -> dict:
    tracks = tracking.get("tracks", []) if tracking.get("status") == "completed" else []
    if not tracks:
        return {"status": "unavailable", "track_id": None,
                "note": "No tracked vehicles or tracker unavailable."}
    # General YOLO tracks do not verify make, color or shoulder relation.
    # Avoid selecting one track just because it is the only car in the scene.
    return {"status": "requires_review", "track_id": None,
            "candidate_track_ids": [track["track_id"] for track in tracks[:20]],
            "note": "No calibrated vehicle make/color classifier or reliable track-to-speech link yet."}


def assess_potential_events(claim: dict, vision: dict) -> dict:
    if vision.get("status") != "completed":
        return {"status": "unavailable", "conclusion": None, "candidates": [],
                "note": "Qwen visual analysis not executed successfully."}
    data = vision.get("observations") or {}
    events = data.get("potential_events") or []
    candidates = []
    for event in events:
        if event.get("category") not in SUPPORTED:
            continue
        candidates.append({
            "category": event["category"],
            "time_seconds": event.get("approximate_second"),
            "visual_evidence": event["visual_evidence"],
            "driver_also_reported": event["category"] in claim.get("reported_categories", []),
            "uncertainty": event.get("uncertainty"),
            "review_state": "requires_human_review"
        })
    return {"status": "candidate_for_review" if candidates else "inconclusive",
            "conclusion": None, "candidates": candidates,
            "note": "Visual language model outputs are not verified offenses. Frame samples can miss key transitions; review the original video."}
