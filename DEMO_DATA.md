# Demo Data Reference

Live sample responses captured from `https://hackathon.prod.pulsefoundry.ai` using [`scripts/probe_api.py`](scripts/probe_api.py). Full JSON files, in [`demo_outputs/`](demo_outputs/).

---

## Quick verification

**Unix / macOS:**

```bash
pip install -r requirements.txt
python scripts/probe_api.py          # re-fetch all demo outputs
curl -sL https://hackathon.prod.pulsefoundry.ai/health/
curl -s "https://hackathon.prod.pulsefoundry.ai/pcc/patients?facility_id=101" | head -c 500
```

**Windows (PowerShell):** use `curl.exe` — the `curl` alias maps to `Invoke-WebRequest`.

```powershell
pip install -r requirements.txt
python scripts/probe_api.py
curl.exe -sL https://hackathon.prod.pulsefoundry.ai/health/
```

Expected health response:

```json
{"status": "healthy", "service": "hackathon"}
```

Note: `/health` redirects to `/health/` — follow redirects or call the trailing-slash URL directly.

---

## Endpoint → patient ID mapping

| Endpoint | ID parameter | Example |
|---|---|---|
| `GET /pcc/patients` | `facility_id` (101, 102, 103) | `facility_id=101` |
| `GET /pcc/diagnoses` | string `patient_id` | `FA-001` |
| `GET /pcc/coverage` | string `patient_id` | `FA-001` |
| `GET /pcc/notes` | **integer** `id` from patients | `1` |
| `GET /pcc/assessments` | **integer** `id` from patients | `1` |

Using `FA-001` on `/notes` or `1` on `/diagnoses` will not return the expected data.

---

## Live vs documented differences

| Topic | [API.md](API.md) says | Live API returns |
|---|---|---|
| Patients per facility | 100 each | **120 / 90 / 90** (300 total — matches [README.md](README.md)) |
| Assessment `raw_json` | Flat fields (`wound_type`, `length_cm`, …) | Often **nested** `sections[].questions[]` with labeled Q&A pairs |
| `payer_type` on coverage | `"Medicare B"` | `"Medicare"`, `"HMO"`, etc. — use **`payer_code`** (`MCB`, `MCA`, …) for logic |
| Note format vs `note_type` | SPN = structured labels | SPN/HP labels often contain **Envive narrative** text |
| FB-001 internal `id` | Not documented | **`121`** (Facility A ids 1–120, Facility B starts at 121) |

---

## Facility and payer mix (captured 2026-06-28)

| `facility_id` | Patients | ID prefix |
|---|---|---|
| 101 (Facility A) | 120 | `FA-` |
| 102 (Facility B) | 90 | `FB-` |
| 103 (Facility C) | 90 | `FC-` |

Facility A `primary_payer_code` distribution from probe run:

| Code | Count | Meaning |
|---|---|---|
| MCB | 61 | Medicare Part B — primary billing target |
| HMO | 27 | Managed care — typically ineligible |
| MCA | 19 | Medicare Part A |
| MCD | 13 | Medicaid |

---

## Showcase patients

Curated examples in `demo_outputs/` — each prefix matches the probe script label.

| Label | `patient_id` | Internal `id` | Why it matters |
|---|---|---|---|
| `MCB_Envive` | FA-001 | 1 | Active MCB + Envive note + nested assessment |
| `HMO_ineligible` | FA-002 | 2 | HMO coverage — wrong payer |
| `SOAP_note` | FA-030 | 30 | Clean SOAP note + structured assessment sections |
| `Prose_multi_wound` | FA-075 | 75 | Abbreviated prose + two wounds in one note |
| `Facility_B` | FB-001 | 121 | Cross-facility check (Medicaid payer) |

---

## Annotated samples

### Patient roster — FA-001

File: [`demo_outputs/MCB_Envive_FA-001_diagnoses.json`](demo_outputs/MCB_Envive_FA-001_diagnoses.json) (see also `patients_facility_101.json`)

```json
{
  "id": 1,
  "patient_id": "FA-001",
  "first_name": "Agnes",
  "last_name": "Dunbar",
  "primary_payer_code": "MCB",
  "is_new_admission": true
}
```

**Callout:** `primary_payer_code` is a hint only — confirm active MCB via coverage records (`effective_to == null`).

### Diagnoses — active vs resolved

File: [`demo_outputs/MCB_Envive_FA-001_diagnoses.json`](demo_outputs/MCB_Envive_FA-001_diagnoses.json)

- **Active wound:** `L89.143` — Stage 3 pressure ulcer, right hip
- **Resolved (ignore for billing):** `Z87.891` — history of nicotine dependence

Filter on `clinical_status == "active"` and wound-related ICD-10 prefixes (`L89`, `L97`, etc.).

### Coverage — active Medicare Part B

File: [`demo_outputs/MCB_Envive_FA-001_coverage.json`](demo_outputs/MCB_Envive_FA-001_coverage.json)

```json
{
  "payer_code": "MCB",
  "payer_name": "Medicare Part B",
  "effective_to": null
}
```

Contrast — HMO patient FA-002: [`HMO_ineligible_FA-002_coverage.json`](demo_outputs/HMO_ineligible_FA-002_coverage.json) has `payer_code: "HMO"`.

### Progress notes — four formats

#### 1. Envive narrative (FA-001)

File: [`demo_outputs/MCB_Envive_FA-001_notes.json`](demo_outputs/MCB_Envive_FA-001_notes.json)

Despite `note_type: "Wound (SPN)"`, the body is Envive prose:

```
*Envive Care Conference Review - V 4.0
Wound Status: Pressure Ulcer to Right hip / Measures 2.9 cm x 2.8 cm / Stage: Stage 3
Drainage present - serosanguineous, heavy.
```

**Extraction hints:** parse `Wound Status:` line for type/location/stage; `Measures L x W`; map drainage adjective to `none|light|moderate|heavy`. Depth often missing — check assessment or flag.

#### 2. SOAP (FA-030)

File: [`demo_outputs/SOAP_note_FA-030_notes.json`](demo_outputs/SOAP_note_FA-030_notes.json)

```
Subjective: Patient reports pain at Right heel wound site, rates 8/10.
Objective: Wound assessment performed. Stage 3 pressure ulcer Right heel measures 3.9 cm x 3.6 cm x 0.6 cm.
  Drainage: moderate.
```

**Extraction hints:** regex on Objective line for `measures L x W x D`; drainage under Objective section. Easiest format for `auto_accept` when payer is MCB.

#### 3. Prose + multi-wound (FA-075)

File: [`demo_outputs/Prose_multi_wound_FA-075_notes.json`](demo_outputs/Prose_multi_wound_FA-075_notes.json)

```
Pt seen for wound eval. Arterial Right lower extremity measures aprx 2.1 x 1.3cm, depth 0.5cm.
Min drainage serosanguineous. Heel wound also eval - R heel 1.3x0.8, 0.2cm deep, slight serous.
```

**Callout:** two wounds in one note — pick primary (first mentioned / largest / matches diagnosis) or route to `flag_for_review`. FA-075 also has a second SOAP note in the same response (multiple current notes).

#### 4. Prose shorthand (FB-001, Facility B)

File: [`demo_outputs/Facility_B_FB-001_notes.json`](demo_outputs/Facility_B_FB-001_notes.json)

```
Wound note - Leftbuttock. Meas 4.4x4.2x1.0cm. Heavy serosang drainage, no odor.
```

Compact single-line format — common outside Facility A.

### Assessments — nested `raw_json`

#### Nested narrative (FA-001)

File: [`demo_outputs/MCB_Envive_FA-001_assessments.json`](demo_outputs/MCB_Envive_FA-001_assessments.json)

`raw_json` parses to:

```json
{
  "sections": [{
    "sectionName": "WOUND_INFO",
    "questions": [{
      "question": "Wound narrative",
      "answer": "Pressure Ulcer to Right hip / Measures 2.9 cm x 2.8 cm / Stage: Stage 3 / Drainage: serosanguineous, heavy"
    }]
  }]
}
```

Run the same text parser as notes, or extract from the narrative answer string.

#### Structured sections (FA-030)

File: [`demo_outputs/SOAP_note_FA-030_assessments.json`](demo_outputs/SOAP_note_FA-030_assessments.json)

Sections include `LOCATION`, `WOUND`, `DRAINAGE`, `WOUND_BED` with explicit Q&A:

| Question | Answer |
|---|---|
| Wound Type | Pressure Ulcer |
| Stage | Stage 3 |
| Length (cm) | 3.9 |
| Width (cm) | 3.6 |
| Depth (cm) | 0.6 |
| Drainage Amount | Moderate |

**Parser strategy:** try flat JSON first; if `sections` key exists, build a `{question: answer}` map from all sections.

---

## Note format cheat sheet

| Format | Detection signal | Example patient | Difficulty |
|---|---|---|---|
| Envive | `*Envive Care Conference Review` or `Wound Status:` slash-delimited line | FA-001, FA-002 | Medium — structured-ish but embedded in prose |
| SOAP | `Subjective:` / `Objective:` / `Assessment:` / `Plan:` | FA-030 | Low |
| Prose | `Meas`, `aprx`, `x` dimensions without labels | FA-075, FB-001 | Medium |
| Multi-wound | Multiple anatomical sites or "also eval" | FA-002, FA-075 | High — needs primary-wound logic |

**Do not rely on `note_type` alone** — `Wound (SPN)` frequently contains Envive text.

---

## Suggested routing examples

Illustrative decisions for the showcase patients (your pipeline rules may differ):

| Patient | Payer | Wound data quality | Suggested routing | Reason |
|---|---|---|---|---|
| FA-001 | MCB | Envive note L×W, no depth in note; assessment has narrative | `flag_for_review` | Eligible payer but depth only in assessment narrative; confirm before billing |
| FA-002 | HMO | Envive + multi-wound prose note | `reject` | No active Medicare Part B coverage |
| FA-030 | HMO | SOAP + structured assessment with full L×W×D | `reject` | Extraction is clean but payer is HMO — not billable under Part B |
| FA-075 | MCA | Prose, two wounds, two notes | `reject` | Medicare Part A only — wrong benefit for outpatient wound billing |
| FB-001 | MCD | Prose with full measurements | `reject` | Medicaid — not Medicare Part B |

If FA-030 had MCB coverage, the SOAP + structured assessment combination would be a strong `auto_accept` candidate.

---

## Rate limiting

Every request has a ~30% chance of HTTP 429. The probe script retries using the `Retry-After` header (1–5 seconds). A typical probe run: ~31 requests, ~7 rate-limit retries, ~2–3 minutes.

Always wrap API calls in retry logic — see `fetch_with_retry()` in [`scripts/probe_api.py`](scripts/probe_api.py).

---

## Output file index

| File | Contents |
|---|---|
| `health.json` | Service health check |
| `patients_facility_{101,102,103}.json` | Full patient rosters |
| `{label}_{patient_id}_diagnoses.json` | ICD-10 diagnoses |
| `{label}_{patient_id}_coverage.json` | Insurance coverage |
| `{label}_{patient_id}_notes.json` | Progress notes |
| `{label}_{patient_id}_assessments.json` | Wound assessments |

Re-generate anytime: `python scripts/probe_api.py`
