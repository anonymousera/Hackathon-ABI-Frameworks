# ABI Frameworks Hackathon

The dashboard is deployed at : https://anonymousera-hackathon-abi-frameworks-srcdashboard-era-b7nlov.streamlit.app/ 

## Running This Implementation

End-to-end: ingest from the PCC API → extract wound fields → route each patient → view in the dashboard.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) enable the LLM extraction fallback for hard-to-parse notes
#    Without this, the pipeline runs rules-only — no LLM calls are made.
export OPENAI_API_KEY=sk-...        # Windows PowerShell: $env:OPENAI_API_KEY="sk-..."

# 3. Run the pipeline.
#    Ingests from the live API via src/database1.py (handles 429 rate limiting),
#    then extracts, routes, and writes patient_eligibility.csv.
python scripts/run_pipeline.py

#    Re-run without re-fetching from the API (reuse the existing hackathon.db):
python scripts/run_pipeline.py --skip-ingest

# 4. Launch the biller dashboard (reads patient_eligibility.csv)
streamlit run src/dashboard.py
```

**Pipeline layout:**

| Component | File | Role |
|---|---|---|
| Ingestion | `src/database1.py` | Fetch all entities from the PCC API into `hackathon.db` (429 retry) |
| DB access | `src/db.py` | Load the SQLite tables into DataFrames |
| Extraction | `src/extract_notes.py`, `src/extract_assessment.py` | Pull wound fields from free-text notes and structured assessments |
| LLM fallback | `src/extract_llm.py` | Parse notes regex can't handle (gated on `OPENAI_API_KEY`) |
| Routing | `src/eligibility.py` | MCB coverage check + `auto_accept` / `flag_for_review` / `reject` |
| Orchestrator | `scripts/run_pipeline.py` | Runs ingest → extract → route → `patient_eligibility.csv` |
| Dashboard | `src/dashboard.py` | Streamlit biller view of the routing decisions |

Detailed system architecture can be found in [wound_care_pipeline_plan.md](https://github.com/anonymousera/Hackathon-ABI-Frameworks/blob/era/wound_care_pipeline_plan.md) and [pcc_pipeline_flowchart](https://github.com/anonymousera/Hackathon-ABI-Frameworks/blob/era/pcc_pipeline_flowchart.png).

---

## The Challenge

You are building a data pipeline for a post-acute care company that needs to identify which patients qualify for wound care billing under Medicare Part B.

Patient data lives in an EHR system called PointClickCare (PCC). Your pipeline will pull from a mock PCC API, extract clinical wound details from free-text notes and structured assessments, and produce a clean output that tells a biller which patients to act on — and why.

The API is rate-limited and will occasionally refuse requests. Your pipeline must handle that gracefully.

---

## Background

Wound care billing under Medicare Part B requires that a patient has:

1. An **active wound** (pressure ulcer, diabetic foot ulcer, venous ulcer, etc.)
2. **Active Medicare Part B coverage**
3. Documented wound measurements (length, width, depth) and drainage level

A biller reviews eligible patients and decides whether to submit a claim. Your job is to automate the data collection and triage steps that currently happen manually.

**Routing decisions:**

| Decision | Meaning |
|---|---|
| `auto_accept` | All required fields are clearly documented — safe to route to billing |
| `flag_for_review` | Data is ambiguous or incomplete — a clinician or biller should review |
| `reject` | Reliable extraction is not possible — do not route to billing |

---

## The Data

The API exposes **300 synthetic patients** across three facilities. No real PHI is used.

| Facility | `facility_id` | Patients |
|---|---|---|
| Facility A | `101` | 120 |
| Facility B | `102` | 90 |
| Facility C | `103` | 90 |

**Payer mix:** ~60% Medicare Part B, ~15% Medicare Part A, ~10% Medicaid, ~15% HMO. Only Medicare Part B patients are eligible for the billing workflow.

**Note formats you will encounter:**

| Format | Description |
|---|---|
| SOAP | Fully structured — wound type, stage, and dimensions are explicit labeled fields |
| Prose | Abbreviated free text with shorthand like `Meas 4.2x3.1x1.5cm` |
| Multi-wound | Describes two wounds; you must identify the primary wound |
| Envive | All clinical details packed into a single unstructured narrative paragraph |

**Wound types:** pressure ulcer (stages 2–4 and unstageable), diabetic foot ulcer, venous stasis ulcer, arterial ulcer, surgical site infection, abscess, burn.

---

## The API

**Base URL:** `https://hackathon.prod.pulsefoundry.ai`

Full endpoint documentation is in [API.md](./API.md). The short version:

| Endpoint | What it returns |
|---|---|
| `GET /pcc/patients?facility_id=101` | All patients for a facility |
| `GET /pcc/diagnoses?patient_id=FA-001` | ICD-10 diagnoses for a patient |
| `GET /pcc/coverage?patient_id=FA-001` | Insurance coverage records |
| `GET /pcc/notes?patient_id=1` | Free-text clinical progress notes |
| `GET /pcc/assessments?patient_id=1` | Structured wound assessment forms |

**Important — two patient identifiers:**
- `patient_id` (string, e.g. `FA-001`) — use this for `/diagnoses` and `/coverage`
- `id` (integer, e.g. `1`) — use this for `/notes` and `/assessments`

Both are returned by the `/patients` endpoint.

**Rate limiting:** Every request has a **30% chance of returning HTTP 429**. The response includes a `Retry-After` header. You must implement retry logic — pipelines that don't handle 429s will fail to load data. See [API.md](./API.md) for recommended retry patterns.

**Verify the API and explore sample data:** run `pip install -r requirements.txt && python scripts/probe_api.py`, then read [DEMO_DATA.md](./DEMO_DATA.md) for annotated live responses and format notes.

---

## What to Build

### Required

**1. Data ingestion pipeline**
Fetch all patients, diagnoses, coverage, notes, and assessments from the API. Handle rate limiting. Store the results somewhere queryable (a local database, dataframe, files — your choice).

**2. Wound data extraction**
From each progress note and assessment, extract:
- Wound type
- Wound stage (for pressure ulcers)
- Location
- Measurements: length, width, depth (cm)
- Drainage amount (`none` / `light` / `moderate` / `heavy`)

**3. Eligibility output table**
Produce one row per patient with:
- Extracted wound fields (above)
- Whether the patient has active Medicare Part B coverage
- A routing decision: `auto_accept`, `flag_for_review`, or `reject`
- A plain-English reason for the decision

**4. Presentation**
Walk us through your output as if presenting to a non-technical biller. What do they see? How do they know what to act on?

**5. Visual output**
Display your results in a visual format — a dashboard, UI, or interactive table. A biller should be able to see patient routing decisions at a glance without reading raw data.

### Optional / Bonus

- Use an LLM or agent to assist with extraction or generate a summary narrative per patient
- Implement incremental sync using the `since` parameter (only fetch records modified since your last run)

---

## Judging Criteria

| Area | What we're looking for |
|---|---|
| **Pipeline design** | Does it handle API failures gracefully? Is the data flow clear and maintainable? |
| **Extraction accuracy** | Are wound fields correctly pulled from both structured and free-text notes? |
| **Schema & data modeling** | Is the output well-structured and easy to query? |
| **Presentation** | Can you explain your output to a non-technical audience? Is the routing logic easy to follow? |
| **Problem-solving approach** | How did you handle ambiguous cases? What tradeoffs did you make? |

There is no single correct solution. We care more about your reasoning and methodology than a perfect accuracy score. Be prepared to explain your decisions.

---

## Submission

At the end of the session, you will present your work. Plan for roughly **10 minutes**: a brief walkthrough of your pipeline architecture, a demo of your output table, and a few example patients showing your routing decisions.

Bring any questions — we're available throughout.

Good luck.
