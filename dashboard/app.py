import os
import requests
import streamlit as st

base = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
st.title("Project Management MAS Dashboard")

if st.button("Refresh health"):
    st.json(requests.get(f"{base}/health", timeout=5).json())

st.subheader("Run pipeline")
title = st.text_input("Title", "Implement auth")
desc = st.text_area("Description", "Build login and roles")
days = st.number_input("Due days", 1, 365, 7)
hours = st.number_input("Estimated hours", 1, 400, 40)
budget = st.number_input("Budget", 100.0, 1000000.0, 5000.0)

if st.button("Run"):
    payload = {"title": title, "description": desc, "due_days": int(days), "estimated_hours": int(hours), "budget": float(budget)}
    st.json(requests.post(f"{base}/run", json=payload, timeout=60).json())
