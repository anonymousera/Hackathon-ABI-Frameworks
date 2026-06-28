import time
import requests
import pandas as pd
import sqlite3

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"
DB_NAME = "hackathon.db"


def get_json(url, max_retries=10):
    for attempt in range(max_retries):
        response = requests.get(url)

        if response.status_code == 200:
            return response.json()

        elif response.status_code == 429:
            retry = int(response.headers.get("Retry-After", 2))
            print(f"429 Rate Limited... wait {retry}s | attempt {attempt + 1}/{max_retries}")
            time.sleep(retry)

        else:
            print(f"Error {response.status_code}: {url}")
            print(response.text)
            return []

    print(f"Failed after {max_retries} retries: {url}")
    return []


conn = sqlite3.connect(DB_NAME)

all_patients = []

for facility in [101, 102, 103]:
    print(f"Fetching patients from facility {facility}...")
    url = f"{BASE_URL}/pcc/patients?facility_id={facility}"
    patients = get_json(url)

    if patients:
        all_patients.extend(patients)

patients_df = pd.DataFrame(all_patients)

print("Patients loaded:")
print(patients_df.head())
print("Total patients:", len(patients_df))

patients_df.to_sql(
    "patients",
    conn,
    if_exists="replace",
    index=False
)

all_diagnoses = []
all_coverages = []
all_notes = []
all_assessments = []

for i, patient in patients_df.iterrows():
    patient_id = patient["patient_id"]
    internal_id = patient["id"]

    print(f"Processing {i + 1}/{len(patients_df)}: {patient_id}")

    diagnoses = get_json(
        f"{BASE_URL}/pcc/diagnoses?patient_id={patient_id}"
    )

    coverage = get_json(
        f"{BASE_URL}/pcc/coverage?patient_id={patient_id}"
    )

    notes = get_json(
        f"{BASE_URL}/pcc/notes?patient_id={internal_id}"
    )

    assessments = get_json(
        f"{BASE_URL}/pcc/assessments?patient_id={internal_id}"
    )

    all_diagnoses.extend(diagnoses)
    all_coverages.extend(coverage)
    all_notes.extend(notes)
    all_assessments.extend(assessments)

    time.sleep(0.2)


diagnoses_df = pd.DataFrame(all_diagnoses)
coverage_df = pd.DataFrame(all_coverages)
notes_df = pd.DataFrame(all_notes)
assessments_df = pd.DataFrame(all_assessments)

diagnoses_df.to_sql(
    "diagnoses",
    conn,
    if_exists="replace",
    index=False
)

coverage_df.to_sql(
    "coverage",
    conn,
    if_exists="replace",
    index=False
)

notes_df.to_sql(
    "notes",
    conn,
    if_exists="replace",
    index=False
)

assessments_df.to_sql(
    "assessments",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print("Database build complete.")
print("Saved to:", DB_NAME)
print("Tables created:")
print("- patients:", len(patients_df))
print("- diagnoses:", len(diagnoses_df))
print("- coverage:", len(coverage_df))
print("- notes:", len(notes_df))
print("- assessments:", len(assessments_df))