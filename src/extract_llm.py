"""LLM fallback for notes the regex parser cannot handle reliably.

Gated behind OPENAI_API_KEY. If the key or the openai package is missing,
extract_with_llm() returns None and the caller keeps the regex result.
"""
import json
import os

_PROMPT = """You extract wound-care fields from a clinical progress note.
Return ONLY a JSON object with these keys (use null when not stated):
  wound_type: one of Pressure Ulcer, Diabetic Foot Ulcer, Venous Stasis Ulcer,
    Arterial Ulcer, Surgical Site Infection, Abscess, Burn (or null)
  wound_stage: integer 1-4 for pressure ulcers, else null
  location: body site string
  length_cm, width_cm, depth_cm: numbers in cm
  drainage_amount: one of none, light, moderate, heavy
If the note describes multiple wounds, extract the primary (first/largest) one.

NOTE:
{note_text}
"""


def extract_with_llm(note_text: str) -> dict | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not (note_text or "").strip():
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": _PROMPT.format(note_text=note_text)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(response.choices[0].message.content)
    except Exception as exc:  # network, parse, auth — fall back to regex result
        print(f"LLM extraction failed, keeping regex result: {exc}")
        return None

    def num(key):
        try:
            return float(data[key]) if data.get(key) is not None else None
        except (TypeError, ValueError):
            return None

    drainage = (data.get("drainage_amount") or "").strip().lower() or None
    if drainage not in (None, "none", "light", "moderate", "heavy"):
        drainage = None

    return {
        "wound_type": data.get("wound_type"),
        "wound_stage": int(data["wound_stage"]) if isinstance(data.get("wound_stage"), (int, float)) else None,
        "location": data.get("location"),
        "length_cm": num("length_cm"),
        "width_cm": num("width_cm"),
        "depth_cm": num("depth_cm"),
        "drainage_amount": drainage,
        "note_format": "llm",
        "is_multi_wound": False,
        "confidence": 0.65,
    }
