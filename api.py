from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from db import record_scan

app = FastAPI(title="Build Club Vision AI Ingestion API")


class ScanPayload(BaseModel):
    member_name: str
    project_name: str = "Unassigned Project"


@app.get("/")
def root():
    return {"status": "online", "system": "Build Club Vision AI Ingestion Engine"}


@app.post("/api/scan")
def process_scan(payload: ScanPayload):
    """API endpoint called when camera detects a face."""
    if not payload.member_name.strip():
        raise HTTPException(status_code=400, detail="Member name cannot be empty.")

    action, timestamp = record_scan(payload.member_name, payload.project_name)
    return {
        "status": "success",
        "member_name": payload.member_name,
        "action": action,
        "timestamp": timestamp,
    }