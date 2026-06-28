import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load OPENAI_API_KEY (and any other vars) from a local .env file if present.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT_DIR, ".env"))
except ImportError:
    pass

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"
FACILITY_IDS = [101, 102, 103]

DB_PATH = os.path.join(ROOT_DIR, "hackathon.db")
OUTPUT_CSV = os.path.join(ROOT_DIR, "patient_eligibility.csv")

CSV_PATHS = {
    "patients": os.path.join(ROOT_DIR, "patients.csv"),
    "diagnoses": os.path.join(ROOT_DIR, "diagnoses.csv"),
    "coverage": os.path.join(ROOT_DIR, "coverage.csv"),
    "notes": os.path.join(ROOT_DIR, "notes.csv"),
    "assessments": os.path.join(ROOT_DIR, "assessments.csv"),
}

# Medicare Part B payer code (payer_code field on coverage records)
MCB_PAYER_CODE = "MCB"

# Wound-related ICD-10 prefixes used as supporting evidence
WOUND_ICD10_PREFIXES = ("L89", "L97", "E11.62", "I83", "I70", "T31", "L08")

CONFIDENCE_AUTO_ACCEPT_MIN = 0.80
