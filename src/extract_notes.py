"""Regex-based wound field extraction from free-text progress notes.

Handles the four documented formats: SOAP, Envive narrative, prose, and
prose with multiple wounds.
"""
import re

WOUND_TYPE_PATTERN = (
    r"(Pressure Ulcer|Diabetic Foot Ulcer|Venous Stasis Ulcer|Venous Ulcer|"
    r"Arterial Ulcer|Arterial|Surgical Site Infection|Abscess|Burn)"
)

DRAINAGE_WORDS = {
    "none": "none",
    "no": "none",
    "minimal": "light",
    "min": "light",
    "slight": "light",
    "light": "light",
    "scant": "light",
    "moderate": "moderate",
    "mod": "moderate",
    "heavy": "heavy",
    "copious": "heavy",
    "large": "heavy",
}

WOUND_TYPE_NORMALIZE = {
    "arterial": "Arterial Ulcer",
    "arterial ulcer": "Arterial Ulcer",
    "pressure ulcer": "Pressure Ulcer",
    "diabetic foot ulcer": "Diabetic Foot Ulcer",
    "venous stasis ulcer": "Venous Stasis Ulcer",
    "venous ulcer": "Venous Stasis Ulcer",
    "surgical site infection": "Surgical Site Infection",
    "abscess": "Abscess",
    "burn": "Burn",
}


def _normalize_wound_type(raw: str) -> str:
    return WOUND_TYPE_NORMALIZE.get(raw.strip().lower(), raw.strip().title())


def _normalize_drainage(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    for word, amount in DRAINAGE_WORDS.items():
        if word in raw:
            return amount
    return None


def _detect_format(text: str) -> str:
    if "Envive Care Conference Review" in text or "Wound Status:" in text:
        return "envive"
    if re.search(r"\bSubjective:|\bObjective:", text):
        return "soap"
    if "also eval" in text.lower() or text.lower().count("measures") > 1 or text.lower().count("meas") > 1:
        return "multi_wound"
    return "prose"


def _find_wound_blocks(text: str) -> list[dict]:
    """Find every (type/location, L, W, D, stage, drainage) tuple mentioned in the text."""
    blocks = []

    # Envive: "Wound Status: <type> to <location> / Measures L cm x W cm / Stage: <stage>"
    for m in re.finditer(
        rf"{WOUND_TYPE_PATTERN}\s+to\s+([A-Za-z ]+?)\s*/\s*Measures\s+([\d.]+)\s*cm\s*x\s*([\d.]+)\s*cm"
        rf"(?:\s*/\s*Stage:\s*(Stage\s*\d+|N/A))?",
        text,
        re.IGNORECASE,
    ):
        blocks.append({
            "wound_type": _normalize_wound_type(m.group(1)),
            "location": m.group(2).strip(),
            "length_cm": float(m.group(3)),
            "width_cm": float(m.group(4)),
            "depth_cm": None,
            "stage": m.group(5).strip() if m.group(5) and "n/a" not in m.group(5).lower() else None,
        })

    # SOAP / generic: "<type> <location> measures L cm x W cm x D cm" (D optional)
    for m in re.finditer(
        rf"{WOUND_TYPE_PATTERN}\s*(?:\w+\s+)?([A-Za-z ]+?)\s+measures\s+([\d.]+)\s*cm\s*x\s*([\d.]+)\s*cm"
        rf"(?:\s*x\s*([\d.]+)\s*cm)?",
        text,
        re.IGNORECASE,
    ):
        blocks.append({
            "wound_type": _normalize_wound_type(m.group(1)),
            "location": m.group(2).strip(),
            "length_cm": float(m.group(3)),
            "width_cm": float(m.group(4)),
            "depth_cm": float(m.group(5)) if m.group(5) else None,
            "stage": None,
        })

    # Prose: "<type> <location> measures aprx L x W cm, depth D cm"
    for m in re.finditer(
        rf"{WOUND_TYPE_PATTERN}\s+([A-Za-z ]+?)\s+measures\s+aprx\s+([\d.]+)\s*x\s*([\d.]+)\s*cm"
        rf"(?:,?\s*depth\s+([\d.]+)\s*cm)?",
        text,
        re.IGNORECASE,
    ):
        blocks.append({
            "wound_type": _normalize_wound_type(m.group(1)),
            "location": m.group(2).strip(),
            "length_cm": float(m.group(3)),
            "width_cm": float(m.group(4)),
            "depth_cm": float(m.group(5)) if m.group(5) else None,
            "stage": None,
        })

    # Secondary "also eval" wound mentioned without explicit wound type:
    # "<Location> wound also eval - <location> LxW, Dcm deep, <drainage> serous"
    for m in re.finditer(
        r"also eval\s*-\s*([A-Za-z .]+?)\s+([\d.]+)x([\d.]+),?\s*([\d.]+)cm\s*deep,?\s*([A-Za-z]+)?",
        text,
        re.IGNORECASE,
    ):
        blocks.append({
            "wound_type": None,
            "location": m.group(1).strip(),
            "length_cm": float(m.group(2)),
            "width_cm": float(m.group(3)),
            "depth_cm": float(m.group(4)),
            "stage": None,
            "drainage_amount": _normalize_drainage(m.group(5)),
        })

    # Compact shorthand: "Wound note - <Location>. Meas LxWxDcm."
    for m in re.finditer(
        r"Wound note\s*-\s*([A-Za-z ]+?)\.\s*Meas\s+([\d.]+)x([\d.]+)x([\d.]+)\s*cm",
        text,
        re.IGNORECASE,
    ):
        blocks.append({
            "wound_type": None,
            "location": m.group(1).strip(),
            "length_cm": float(m.group(2)),
            "width_cm": float(m.group(3)),
            "depth_cm": float(m.group(4)),
            "stage": None,
        })

    return blocks


def _find_drainage(text: str) -> str | None:
    m = re.search(r"Drainage[: ]+(?:present\s*-\s*)?\(?([A-Za-z, ]+?)[.\n]", text, re.IGNORECASE)
    if m:
        amount = _normalize_drainage(m.group(1))
        if amount:
            return amount
    m = re.search(r"\b(none|no|minimal|min|slight|light|scant|moderate|mod|heavy|copious)\b[^.\n]*drainage", text, re.IGNORECASE)
    if m:
        return _normalize_drainage(m.group(1))
    return None


def extract_from_note(note_text: str) -> dict:
    """Return the best single wound record extracted from one note's text."""
    text = note_text or ""
    note_format = _detect_format(text)
    blocks = _find_wound_blocks(text)

    if not blocks:
        return {
            "wound_type": None, "wound_stage": None, "location": None,
            "length_cm": None, "width_cm": None, "depth_cm": None,
            "drainage_amount": None, "note_format": note_format,
            "is_multi_wound": False, "confidence": 0.0,
        }

    # Pick primary wound: prefer the first block that has an explicit wound_type
    primary = next((b for b in blocks if b.get("wound_type")), blocks[0])
    is_multi = len(blocks) > 1

    drainage = primary.get("drainage_amount") or _find_drainage(text)
    stage_str = primary.get("stage")
    stage = int(re.search(r"\d+", stage_str).group()) if stage_str and re.search(r"\d+", stage_str) else None

    confidence_by_format = {"soap": 0.85, "prose": 0.70, "multi_wound": 0.60, "envive": 0.65}
    confidence = confidence_by_format.get(note_format, 0.5)

    fields_present = sum(
        1 for v in (primary.get("wound_type"), primary["location"], primary["length_cm"],
                     primary["width_cm"], primary["depth_cm"], drainage) if v is not None
    )
    if fields_present < 4:
        confidence -= 0.15
    if is_multi:
        confidence -= 0.1

    return {
        "wound_type": primary.get("wound_type"),
        "wound_stage": stage,
        "location": primary["location"],
        "length_cm": primary["length_cm"],
        "width_cm": primary["width_cm"],
        "depth_cm": primary["depth_cm"],
        "drainage_amount": drainage,
        "note_format": note_format,
        "is_multi_wound": is_multi,
        "confidence": round(max(confidence, 0.0), 2),
    }
