"""Streamlit biller-facing dashboard for patient_eligibility output."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from src.config import OUTPUT_CSV

st.set_page_config(page_title="Wound Care Billing Triage", layout="wide")

st.title("Wound Care Billing Triage")
st.caption("Medicare Part B wound care eligibility — auto-generated from PCC clinical notes and assessments.")

if not Path(OUTPUT_CSV).exists():
    st.error(f"No output found at {OUTPUT_CSV}. Run `python scripts/run_pipeline.py` first.")
    st.stop()

df = pd.read_csv(OUTPUT_CSV)

DECISION_COLORS = {"auto_accept": "#1a7f37", "flag_for_review": "#b08900", "reject": "#c1121f"}
DECISION_LABELS = {"auto_accept": "Ready to bill", "flag_for_review": "Needs review", "reject": "Not billable"}

counts = df["routing_decision"].value_counts()
cols = st.columns(4)
cols[0].metric("Total patients", len(df))
cols[1].metric("Ready to bill", int(counts.get("auto_accept", 0)))
cols[2].metric("Needs review", int(counts.get("flag_for_review", 0)))
cols[3].metric("Not billable", int(counts.get("reject", 0)))

st.divider()

filter_cols = st.columns(4)
facility_filter = filter_cols[0].multiselect("Facility", sorted(df["facility_id"].unique()))
decision_filter = filter_cols[1].multiselect(
    "Routing decision", list(DECISION_LABELS.keys()), format_func=lambda d: DECISION_LABELS[d]
)
mcb_filter = filter_cols[2].selectbox("Medicare Part B", ["All", "Active only", "Inactive only"])
search = filter_cols[3].text_input("Search by name or patient ID")

filtered = df.copy()
if facility_filter:
    filtered = filtered[filtered["facility_id"].isin(facility_filter)]
if decision_filter:
    filtered = filtered[filtered["routing_decision"].isin(decision_filter)]
if mcb_filter == "Active only":
    filtered = filtered[filtered["has_active_mcb"]]
elif mcb_filter == "Inactive only":
    filtered = filtered[~filtered["has_active_mcb"]]
if search:
    needle = search.lower()
    filtered = filtered[
        filtered["patient_name"].str.lower().str.contains(needle)
        | filtered["patient_id"].str.lower().str.contains(needle)
    ]


def decision_badge(decision: str) -> str:
    color = DECISION_COLORS.get(decision, "#666")
    label = DECISION_LABELS.get(decision, decision)
    return f"<span style='background:{color};color:white;padding:2px 8px;border-radius:8px;font-size:0.85em'>{label}</span>"


display_df = filtered[[
    "patient_name", "patient_id", "facility_id", "wound_type", "location",
    "length_cm", "width_cm", "depth_cm", "drainage_amount",
    "has_active_mcb", "routing_decision", "reason", "confidence",
]].rename(columns={
    "patient_name": "Patient", "patient_id": "PCC ID", "facility_id": "Facility",
    "wound_type": "Wound Type", "location": "Location",
    "length_cm": "L (cm)", "width_cm": "W (cm)", "depth_cm": "D (cm)",
    "drainage_amount": "Drainage", "has_active_mcb": "Medicare Part B",
    "routing_decision": "Decision", "reason": "Reason", "confidence": "Confidence",
})

st.subheader(f"Patients ({len(display_df)})")
st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Patient detail")
selected_id = st.selectbox("Select a patient to inspect", filtered["patient_id"] if not filtered.empty else [])

if selected_id:
    record = filtered[filtered["patient_id"] == selected_id].iloc[0]
    st.markdown(
        f"### {record['patient_name']} ({record['patient_id']}) — Facility {record['facility_id']}",
        unsafe_allow_html=True,
    )
    st.markdown(decision_badge(record["routing_decision"]), unsafe_allow_html=True)
    st.write(f"**Reason:** {record['reason']}")
    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.write("**Wound details**")
        st.write(f"Type: {record['wound_type'] or 'Not documented'}")
        st.write(f"Stage: {record['wound_stage'] if pd.notna(record['wound_stage']) else 'N/A'}")
        st.write(f"Location: {record['location'] or 'Not documented'}")
        st.write(f"Measurements: {record['length_cm']} x {record['width_cm']} x {record['depth_cm']} cm")
        st.write(f"Drainage: {record['drainage_amount'] or 'Not documented'}")
    with detail_cols[1]:
        st.write("**Billing signal**")
        st.write(f"Medicare Part B active: {bool(record['has_active_mcb'])}")
        st.write(f"Active wound diagnosis on file: {bool(record['has_active_wound_dx'])}")
        st.write(f"Extraction source: {record['source']}")
        st.write(f"Extraction confidence: {record['confidence']}")
