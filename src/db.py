"""Read the tables that database1.py ingests into SQLite."""
import sqlite3

import pandas as pd

from src.config import DB_PATH


def load_tables(db_path: str = DB_PATH) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        return {
            "patients": pd.read_sql("SELECT * FROM patients", conn),
            "diagnoses": pd.read_sql("SELECT * FROM diagnoses", conn),
            "coverage": pd.read_sql("SELECT * FROM coverage", conn),
            "notes": pd.read_sql("SELECT * FROM notes", conn),
            "assessments": pd.read_sql("SELECT * FROM assessments", conn),
        }
    finally:
        conn.close()
