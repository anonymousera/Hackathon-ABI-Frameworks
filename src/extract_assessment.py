"""Parse structured/nested assessment raw_json into normalized wound fields."""
import json
import re

from src.extract_notes import extract_from_note

DRAINAGE_AMOUNT_MAP = {"none": "none", "light": "light", "minimal": "light", "moderate": "moderate", "heavy": "heavy"}


def _flatten_qa(raw: dict) -> dict[str, str]:
    qa = {}
    for section in raw.get("sections", []):
        for question in section.get("questions", []):
            label = (question.get("question") or "").strip().lower()
            qa[label] = question.get("answer")
    return qa


def extract_from_assessment(raw_json: str | None, status: str | None) -> dict:
    empty = {
        "wound_type": None, "wound_stage": None, "location": None,
        "length_cm": None, "width_cm": None, "depth_cm": None,
        "drainage_amount": None, "confidence": 0.0,
    }
    if not raw_json:
        return empty

    try:
        raw = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        return empty

    qa = _flatten_qa(raw)

    # Narrative-only assessment (e.g. Envive narrative embedded in a single Q&A) —
    # reuse the note-text parser since the format is identical free text.
    narrative = qa.get("wound narrative")
    if narrative and not qa.get("wound type"):
        parsed = extract_from_note(narrative)
        return {
            "wound_type": parsed["wound_type"],
            "wound_stage": parsed["wound_stage"],
            "location": parsed["location"],
            "length_cm": parsed["length_cm"],
            "width_cm": parsed["width_cm"],
            "depth_cm": parsed["depth_cm"],
            "drainage_amount": parsed["drainage_amount"],
            "confidence": 0.75 if status == "Complete" else 0.55,
        }

    def to_float(key: str) -> float | None:
        val = qa.get(key)
        try:
            return float(val) if val is not None else None
        except ValueError:
            return None

    stage_raw = qa.get("stage")
    stage = None
    if stage_raw and "n/a" not in stage_raw.lower():
        m = re.search(r"\d+", stage_raw)
        stage = int(m.group()) if m else None

    drainage_raw = (qa.get("drainage amount") or "").strip().lower()
    drainage = DRAINAGE_AMOUNT_MAP.get(drainage_raw)
    if drainage is None and qa.get("drainage present", "").strip().lower() == "no":
        drainage = "none"

    fields = {
        "wound_type": qa.get("wound type"),
        "wound_stage": stage,
        "location": qa.get("location"),
        "length_cm": to_float("length (cm)"),
        "width_cm": to_float("width (cm)"),
        "depth_cm": to_float("depth (cm)"),
        "drainage_amount": drainage,
        "raw_assessment":raw_json
    }

    fields_present = sum(1 for v in fields.values() if v is not None)
    base_confidence = 0.95 if status == "Complete" else 0.75
    if fields_present < 5:
        base_confidence -= 0.15 * (5 - fields_present)

    fields["confidence"] = round(max(base_confidence, 0.0), 2)
    return fields
