"""Merge extraction sources per patient, check Medicare Part B coverage, and route."""
from datetime import datetime

import pandas as pd

from src.config import CONFIDENCE_AUTO_ACCEPT_MIN, MCB_PAYER_CODE, WOUND_ICD10_PREFIXES
from src.extract_assessment import extract_from_assessment
from src.extract_notes import extract_from_note

REQUIRED_FIELDS = ("wound_type", "length_cm", "width_cm", "depth_cm", "drainage_amount")


def has_active_mcb(coverage_rows: pd.DataFrame) -> bool:
    for _, row in coverage_rows.iterrows():
        if row.get("payer_code") != MCB_PAYER_CODE:
            continue
        effective_to = row.get("effective_to")
        if pd.isna(effective_to) or effective_to in (None, ""):
            return True
    return False


def has_active_wound_dx(diagnosis_rows: pd.DataFrame) -> bool:
    for _, row in diagnosis_rows.iterrows():
        if row.get("clinical_status") != "active":
            continue
        code = str(row.get("icd10_code") or "")
        if any(code.startswith(prefix) for prefix in WOUND_ICD10_PREFIXES):
            return True
    return False


def best_extraction(notes_rows: pd.DataFrame, assessment_rows: pd.DataFrame) -> dict:
    """Pick the highest-confidence wound extraction across all assessments and notes."""
    candidates = []

    for _, row in assessment_rows.iterrows():
        parsed = extract_from_assessment(row.get("raw_json"), row.get("status"))
        parsed["source"] = "assessment"
        parsed["is_multi_wound"] = False
        candidates.append(parsed)

    current_notes = notes_rows[notes_rows.get("is_current", True) == True] if "is_current" in notes_rows else notes_rows
    if current_notes.empty:
        current_notes = notes_rows

    for _, row in current_notes.iterrows():
        parsed = extract_from_note(row.get("note_text"))
        parsed["source"] = "note"
        candidates.append(parsed)

    if not candidates:
        return {
            "wound_type": None, "wound_stage": None, "location": None,
            "length_cm": None, "width_cm": None, "depth_cm": None,
            "drainage_amount": None, "confidence": 0.0, "source": "none",
            "is_multi_wound": False,
        }

    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    best = candidates[0]

    # Backfill missing fields from the next-best candidate (e.g. assessment narrative
    # supplies depth that the note left out), lowering confidence slightly on conflict.
    for other in candidates[1:]:
        for field in REQUIRED_FIELDS + ("location", "wound_stage"):
            if best.get(field) is None and other.get(field) is not None:
                best[field] = other[field]
        if (
            best.get("length_cm") and other.get("length_cm")
            and abs(best["length_cm"] - other["length_cm"]) / max(best["length_cm"], 1) > 0.2
        ):
            best["confidence"] = round(best["confidence"] - 0.1, 2)

    return best


def route_patient(extraction: dict, mcb_active: bool, wound_dx_active: bool) -> tuple[str, str]:
    fields_present = [extraction.get(f) is not None for f in REQUIRED_FIELDS]
    all_fields_present = all(fields_present)
    any_fields_present = any(fields_present)
    confidence = extraction.get("confidence", 0.0)
    is_multi = extraction.get("is_multi_wound", False)
    source = extraction.get("source", "none")

    if not any_fields_present and not wound_dx_active:
        return "reject", "No wound documentation found in notes or assessments. Cannot route to billing."

    if not mcb_active:
        return "reject", "No active Medicare Part B coverage — patient is not eligible for this billing workflow."

    source_is_reliable = source == "assessment" or (source == "note" and extraction.get("note_format") == "soap")

    if all_fields_present and confidence >= CONFIDENCE_AUTO_ACCEPT_MIN and not is_multi and source_is_reliable:
        desc = (
            f"{extraction.get('wound_type')} ({extraction.get('location')}) "
            f"{extraction.get('length_cm')}x{extraction.get('width_cm')}x{extraction.get('depth_cm')} cm, "
            f"{extraction.get('drainage_amount')} drainage"
        )
        return "auto_accept", f"Medicare Part B active. Wound fully documented ({desc})."

    if not all_fields_present:
        missing = [f for f, present in zip(REQUIRED_FIELDS, fields_present) if not present]
        return "flag_for_review", (
            f"Medicare Part B active but wound documentation is incomplete (missing: {', '.join(missing)}). "
            "Clinician or biller should verify before submitting."
        )

    if is_multi:
        return "flag_for_review", (
            "Medicare Part B active; multiple wounds documented in the same note. "
            "Confirm the primary billable wound before submitting."
        )

    return "flag_for_review", (
        "Medicare Part B active but extraction confidence is low (source: "
        f"{source}, confidence {confidence}). Verify measurements before submitting."
    )


def build_eligibility_table(tables: dict) -> pd.DataFrame:
    patients = tables["patients"]
    diagnoses = tables["diagnoses"]
    coverage = tables["coverage"]
    notes = tables["notes"]
    assessments = tables["assessments"]

    rows = []
    for _, patient in patients.iterrows():
        patient_id = patient["patient_id"]
        internal_id = patient["id"]

        patient_dx = diagnoses[diagnoses["patient_id"] == patient_id]
        patient_cov = coverage[coverage["patient_id"] == patient_id]
        patient_notes = notes[notes["patient_id"] == internal_id]
        patient_assess = assessments[assessments["patient_id"] == internal_id]

        mcb_active = has_active_mcb(patient_cov)
        wound_dx_active = has_active_wound_dx(patient_dx)
        extraction = best_extraction(patient_notes, patient_assess)
        decision, reason = route_patient(extraction, mcb_active, wound_dx_active)

        rows.append({
            "patient_id": patient_id,
            "internal_id": internal_id,
            "facility_id": patient["facility_id"],
            "patient_name": f"{patient['first_name']} {patient['last_name']}",
            "wound_type": extraction.get("wound_type"),
            "wound_stage": extraction.get("wound_stage"),
            "location": extraction.get("location"),
            "length_cm": extraction.get("length_cm"),
            "width_cm": extraction.get("width_cm"),
            "depth_cm": extraction.get("depth_cm"),
            "drainage_amount": extraction.get("drainage_amount"),
            "has_active_mcb": mcb_active,
            "has_active_wound_dx": wound_dx_active,
            "routing_decision": decision,
            "reason": reason,
            "source": extraction.get("source"),
            "confidence": extraction.get("confidence"),
            "processed_at": datetime.utcnow().isoformat(),
            "raw_note":extraction.get("raw_note_text"),
            "raw_assessment":extraction.get("raw_assessment")
        })

    return pd.DataFrame(rows)
