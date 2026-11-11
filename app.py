"""
Learn With Communities Campaign Tracker - FastAPI Backend
Provides REST endpoints and Server-Sent Events (SSE) for real-time profile verification.
"""
import os
import sys
import json
import asyncio
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure root folder is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.campaign import CAMPAIGN_BADGES, evaluate_candidate
from core.scraper import scrape_single_profile, scrape_batch, clean_profile_url
from core.csv_handler import parse_csv_data, export_results_csv
import httpx

app = FastAPI(
    title="Learn With Communities Campaign Tracker",
    description="Credential and Skill Badge Tracker for Google Skills Profiles",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory store for active session results
CURRENT_SESSION = {
    "records": [],
    "results": [],
    "is_scanning": False,
    "last_scanned": None
}


class SingleUrlRequest(BaseModel):
    url: str


class ScanBatchRequest(BaseModel):
    urls: List[str]
    delay: Optional[float] = 0.8
    concurrency: Optional[int] = 2


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Campaign Tracker Backend is Running</h1><p>Visit /static/index.html</p>")


@app.get("/api/campaign-badges")
async def get_campaign_badges():
    """Returns the list of 10 official campaign badges required for completion."""
    return {
        "total_required": len(CAMPAIGN_BADGES),
        "badges": CAMPAIGN_BADGES
    }


@app.get("/api/sample-csv")
async def get_sample_csv():
    """Returns the default sample CSV records provided for the campaign."""
    sample_path = os.path.join(os.path.dirname(__file__), "sample_students.csv")
    if os.path.exists(sample_path):
        records = parse_csv_data(sample_path)
        return {"records": records, "filename": "sample_students.csv"}
    raise HTTPException(status_code=404, detail="Sample CSV not found.")


@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Uploads and parses a CSV roster of students."""
    try:
        contents = await file.read()
        records = parse_csv_data(contents)
        if not records:
            raise HTTPException(status_code=400, detail="No valid URLs found in the uploaded CSV.")
        
        CURRENT_SESSION["records"] = records
        return {
            "success": True,
            "filename": file.filename,
            "total_candidates": len(records),
            "records": records
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process CSV: {str(e)}")


@app.post("/api/check-single")
async def check_single_profile(req: SingleUrlRequest):
    """Scrapes and evaluates a single Google Skills profile URL."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        result = await scrape_single_profile(client, req.url)
        return result


@app.get("/api/scan-stream")
async def scan_stream(delay: float = Query(0.8, ge=0.1, le=5.0), concurrency: int = Query(2, ge=1, le=5)):
    """
    Server-Sent Events (SSE) streaming endpoint:
    Verifies the uploaded records one by one and streams progress in real time.
    """
    records = CURRENT_SESSION.get("records", [])
    if not records:
        # Fallback to sample CSV
        sample_path = os.path.join(os.path.dirname(__file__), "sample_students.csv")
        if os.path.exists(sample_path):
            records = parse_csv_data(sample_path)
            CURRENT_SESSION["records"] = records

    if not records:
        async def empty_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': 'No candidates to scan.'})}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def event_generator():
        total = len(records)
        CURRENT_SESSION["is_scanning"] = True
        CURRENT_SESSION["results"] = []
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"

        async def stream_progress(result_item, count, total_count):
            CURRENT_SESSION["results"].append(result_item)
            payload = {
                "type": "progress",
                "current": count,
                "total": total_count,
                "item": result_item
            }
            return payload

        # Process batch
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            semaphore = asyncio.Semaphore(concurrency)
            count = 0
            for idx, item in enumerate(records):
                async with semaphore:
                    res = await scrape_single_profile(client, item["url"])
                    if "info" in item:
                        res["original_info"] = item["info"]
                    if "name" in item and item["name"]:
                        res["csv_name"] = item["name"]

                    count += 1
                    CURRENT_SESSION["results"].append(res)
                    payload = {
                        "type": "progress",
                        "current": count,
                        "total": total,
                        "item": res
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

                    if idx < total - 1 and delay > 0:
                        await asyncio.sleep(delay)

        CURRENT_SESSION["is_scanning"] = False
        CURRENT_SESSION["last_scanned"] = datetime.now().isoformat()
        
        # Summary statistics
        res_list = CURRENT_SESSION["results"]
        completed = sum(1 for r in res_list if r.get("status") == "COMPLETED")
        in_progress = sum(1 for r in res_list if r.get("status") == "IN_PROGRESS")
        not_started = sum(1 for r in res_list if r.get("status") == "NOT_STARTED")
        private_count = sum(1 for r in res_list if r.get("status") == "PRIVATE_PROFILE")
        errors = sum(1 for r in res_list if r.get("status") == "ERROR")

        summary = {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "not_started": not_started,
            "private": private_count,
            "errors": errors,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0.0
        }

        yield f"data: {json.dumps({'type': 'complete', 'summary': summary})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/results")
async def get_current_results():
    """Returns the latest evaluated candidate results and session status."""
    return {
        "is_scanning": CURRENT_SESSION.get("is_scanning", False),
        "total": len(CURRENT_SESSION.get("results", [])),
        "results": CURRENT_SESSION.get("results", []),
        "last_scanned": CURRENT_SESSION.get("last_scanned")
    }


@app.get("/api/export/csv")
async def export_csv():
    """Generates and downloads the verified candidate roster as a CSV."""
    results = CURRENT_SESSION.get("results", [])
    if not results:
        raise HTTPException(status_code=400, detail="No scan results available to export.")
    
    csv_content = export_results_csv(results)
    filename = f"campaign_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/export/json")
async def export_json():
    """Exports results in JSON format."""
    results = CURRENT_SESSION.get("results", [])
    return JSONResponse(content={"results": results, "exported_at": datetime.now().isoformat()})
