"""Single-operator review storage and validation for preliminary evidence."""
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field


class ReviewUpdate(BaseModel):
    # These statuses explicitly do NOT mean a traffic offense is proven.
    status: Literal["unreviewed", "needs_review", "reviewed_no_conclusion"] = "needs_review"
    manual_description: str = Field(default="", max_length=500)
    selected_track_id: int | None = Field(default=None, ge=0)
    reviewed_event_second: float | None = Field(default=None, ge=0)
    review_note: str = Field(default="", max_length=1000)


def default_review():
    return {
        "status": "unreviewed", "manual_description": "",
        "selected_track_id": None, "reviewed_event_second": None,
        "review_note": "", "updated_at": None,
    }


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS incident_reviews (
        incident_id TEXT PRIMARY KEY REFERENCES incidents(id),
        review_json TEXT NOT NULL
    )""")


def read_review(db, incident_id):
    row = db.execute("SELECT review_json FROM incident_reviews WHERE incident_id=?",
                     (incident_id,)).fetchone()
    return json.loads(row[0]) if row else default_review()


def write_review(db, incident_id, update: ReviewUpdate, duration: float, analysis: dict):
    if update.reviewed_event_second is not None and update.reviewed_event_second > duration:
        raise HTTPException(422, "Event time must be within analyzed clip")
    if update.selected_track_id is not None:
        tracks = (analysis.get("object_tracking") or {}).get("tracks") or []
        if not any(t.get("track_id") == update.selected_track_id for t in tracks):
            raise HTTPException(422, "Track ID is not present in this recording")
    old = read_review(db, incident_id)
    updated = {**update.model_dump(),
               "updated_at": datetime.now(timezone.utc).isoformat()}
    db.execute("""INSERT INTO incident_reviews (incident_id, review_json)
        VALUES (?,?) ON CONFLICT(incident_id) DO UPDATE
        SET review_json=excluded.review_json""",
        (incident_id, json.dumps(updated, ensure_ascii=False)))
    return updated, update.manual_description != old.get("manual_description", "")
