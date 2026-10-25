import os
from services.api.assessment import assess_potential_events, match_target
from services.api.intent import parse_driver_claim
from services.api.qwen import parse_json_response, describe_video
from services.api.plate import scan_plates
from services.api.tracker import track_vehicles


def test_claim_is_not_visual_fact():
    claim = parse_driver_claim("Take photo, blue Kia on the left shoulder")
    assert claim["reported_categories"] == ["shoulder_driving"]
    assert claim["color"] == "blue"
    assert claim["make"] == "kia"
    assert claim["verified_from_video"] is False


def test_arabic_traffic_claim():
    claim = parse_driver_claim("العربية كيا الزرقاء قطعت الإشارة الحمراء")
    assert claim["reported_categories"] == ["red_light"]
    assert claim["make"] == "kia"
    assert claim["color"] == "blue"


def test_qwen_json_sanitization_and_no_fabrication():
    output = parse_json_response('{"scene_summary":"Road", "potential_events":[{"category":"red_light","visual_evidence":"red signal visible","approximate_second":4},{"category":"unsafe_other","visual_evidence":"foo"}]}')
    assert output["scene_summary"] == "Road"
    assert len(output["potential_events"]) == 1
    assert output["potential_events"][0]["requires_human_review"]
    assert parse_json_response("not-json") is None


def test_candidate_is_unverified_even_if_claim_agrees():
    claim = parse_driver_claim("Take photo, red light")
    vision = {"status":"completed", "observations":{"potential_events":[
        {"category":"red_light", "visual_evidence":"Red signal with car", "approximate_second":3,
         "uncertainty":"Stop line unclear"}]}}
    candidate = assess_potential_events(claim, vision)
    assert candidate["status"] == "candidate_for_review"
    assert candidate["conclusion"] is None
    assert candidate["candidates"][0]["review_state"] == "requires_human_review"
    assert match_target(claim, {"status":"completed","tracks":[{"track_id":3}]})["track_id"] is None


def test_unconfigured_models_not_fake(monkeypatch, tmp_path):
    for name in ["TE_YOLO_MODEL", "TE_PLATE_MODEL", "TE_ENABLE_QWEN"]:
        monkeypatch.delenv(name, raising=False)
    assert track_vehicles(tmp_path/"empty.mp4", {})["status"] == "not_configured"
    assert scan_plates(tmp_path/"empty.mp4", 20)["value"] is None
    assert describe_video(tmp_path/"empty.mp4", 20, {})["status"] == "not_configured"
