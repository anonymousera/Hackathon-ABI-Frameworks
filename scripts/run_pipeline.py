"""CLI entry point: ingest -> extract -> route -> write patient_eligibility output."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATABASE1_SCRIPT = ROOT_DIR / "src" / "database1.py"
sys.path.insert(0, str(ROOT_DIR))

from src.config import OUTPUT_CSV
from src.db import load_tables
from src.eligibility import build_eligibility_table


def main():
    parser = argparse.ArgumentParser(description="Run the wound care billing eligibility pipeline.")
    parser.add_argument(
        "--skip-ingest", action="store_true",
        help="Reuse the existing hackathon.db instead of re-running database1.py against the live API",
    )
    args = parser.parse_args()

    if not args.skip_ingest:
        print(f"Ingesting from the PCC API via {DATABASE1_SCRIPT}...")
        # cwd=ROOT_DIR so database1.py's relative "hackathon.db" lands where src.config expects it
        subprocess.run([sys.executable, str(DATABASE1_SCRIPT)], cwd=ROOT_DIR, check=True)

    print("Loading tables for extraction...")
    tables = load_tables()

    print("Extracting wound fields and routing patients...")
    eligibility_df = build_eligibility_table(tables)

    eligibility_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {len(eligibility_df)} rows to {OUTPUT_CSV}")

    print("\nSummary:")
    print(eligibility_df["routing_decision"].value_counts().to_string())


if __name__ == "__main__":
    main()
