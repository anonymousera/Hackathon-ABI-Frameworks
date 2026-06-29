#!/usr/bin/env python3
"""Probe the hackathon mock PCC API and save showcase demo outputs."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import requests

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "demo_outputs"
FACILITY_IDS = (101, 102, 103)

# Curated showcase patients spanning payer types and note formats.
SHOWCASE_PATIENTS = [
    {"patient_id": "FA-001", "internal_id": 1, "label": "MCB_Envive"},
    {"patient_id": "FA-002", "internal_id": 2, "label": "HMO_ineligible"},
    {"patient_id": "FA-030", "internal_id": 30, "label": "SOAP_note"},
    {"patient_id": "FA-075", "internal_id": 75, "label": "Prose_multi_wound"},
    {"patient_id": "FB-001", "internal_id": 121, "label": "Facility_B"},
]

_stats = {"requests": 0, "retries_429": 0, "retries_error": 0}


def fetch_with_retry(url: str, max_attempts: int = 8) -> object:
    """GET JSON from url, retrying on HTTP 429 and transient network errors."""
    for attempt in range(max_attempts):
        _stats["requests"] += 1
        try:
            resp = requests.get(url, timeout=30)
        except requests.RequestException as exc:
            _stats["retries_error"] += 1
            wait = min(2 ** attempt, 10)
            print(f"  network error on attempt {attempt + 1}: {exc}; sleeping {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            _stats["retries_429"] += 1
            wait = int(resp.headers.get("Retry-After", 3))
            print(f"  429 on attempt {attempt + 1}, sleeping {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Failed after {max_attempts} attempts: {url}")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def probe_health() -> dict:
    data = fetch_with_retry(f"{BASE_URL}/health/")
    write_json(OUTPUT_DIR / "health.json", data)
    return data


def probe_facility_patients(facility_id: int) -> list:
    patients = fetch_with_retry(f"{BASE_URL}/pcc/patients?facility_id={facility_id}")
    write_json(OUTPUT_DIR / f"patients_facility_{facility_id}.json", patients)
    return patients


def probe_patient(patient_id: str, internal_id: int, label: str) -> None:
    prefix = f"{label}_{patient_id}"
    diagnoses = fetch_with_retry(f"{BASE_URL}/pcc/diagnoses?patient_id={patient_id}")
    write_json(OUTPUT_DIR / f"{prefix}_diagnoses.json", diagnoses)

    coverage = fetch_with_retry(f"{BASE_URL}/pcc/coverage?patient_id={patient_id}")
    write_json(OUTPUT_DIR / f"{prefix}_coverage.json", coverage)

    notes = fetch_with_retry(f"{BASE_URL}/pcc/notes?patient_id={internal_id}")
    write_json(OUTPUT_DIR / f"{prefix}_notes.json", notes)

    assessments = fetch_with_retry(f"{BASE_URL}/pcc/assessments?patient_id={internal_id}")
    write_json(OUTPUT_DIR / f"{prefix}_assessments.json", assessments)


def resolve_showcase_patients(all_patients_by_facility: dict[int, list]) -> list[dict]:
    """Match showcase entries to live patient records; resolve FB-001 internal id."""
    resolved = []
    fa_patients = {p["patient_id"]: p for p in all_patients_by_facility.get(101, [])}
    fb_patients = {p["patient_id"]: p for p in all_patients_by_facility.get(102, [])}

    for entry in SHOWCASE_PATIENTS:
        pid = entry["patient_id"]
        if pid.startswith("FB-"):
            record = fb_patients.get(pid)
        else:
            record = fa_patients.get(pid)
        if record is None:
            print(f"WARNING: showcase patient {pid} not found, skipping")
            continue
        resolved.append({**entry, "internal_id": record["id"]})
    return resolved


def print_summary(
    health: dict,
    patients_by_facility: dict[int, list],
    showcase: list[dict],
) -> None:
    print("\n=== API Probe Summary ===")
    print(f"Health: {health}")
    print("\nFacility counts:")
    for fid in FACILITY_IDS:
        pts = patients_by_facility.get(fid, [])
        print(f"  facility_id={fid}: {len(pts)} patients")

    fa_pts = patients_by_facility.get(101, [])
    if fa_pts:
        payer_mix = Counter(p.get("primary_payer_code") for p in fa_pts)
        print("\nFacility A payer mix (primary_payer_code):")
        for code, count in payer_mix.most_common():
            print(f"  {code}: {count}")

    print("\nShowcase patients probed:")
    for entry in showcase:
        notes_path = OUTPUT_DIR / f"{entry['label']}_{entry['patient_id']}_notes.json"
        note_type = "—"
        if notes_path.exists():
            notes = json.loads(notes_path.read_text(encoding="utf-8"))
            if notes:
                note_type = notes[0].get("note_type", "unknown")
        print(f"  {entry['patient_id']} (id={entry['internal_id']}, {entry['label']}): note_type={note_type}")

    print(
        f"\nRequest stats: {_stats['requests']} requests, "
        f"{_stats['retries_429']} rate-limit retries, "
        f"{_stats['retries_error']} network retries"
    )
    print(f"Output directory: {OUTPUT_DIR}")


def main() -> int:
    print("Probing hackathon API...")
    health = probe_health()
    print(f"Health OK: {health}")

    patients_by_facility: dict[int, list] = {}
    for fid in FACILITY_IDS:
        print(f"Fetching patients for facility {fid}...")
        patients_by_facility[fid] = probe_facility_patients(fid)

    showcase = resolve_showcase_patients(patients_by_facility)
    for entry in showcase:
        print(f"Probing {entry['patient_id']} ({entry['label']})...")
        probe_patient(entry["patient_id"], entry["internal_id"], entry["label"])

    print_summary(health, patients_by_facility, showcase)
    return 0


if __name__ == "__main__":
    sys.exit(main())
