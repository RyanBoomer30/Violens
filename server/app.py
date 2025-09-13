import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import time
import os
import shutil
from datetime import datetime

app = FastAPI(title="Social Sentinel Analysis API")

reports_db = []

def run_analysis_model(video_path: str) -> dict:
    print(f"Analyzing video: {video_path}...")
    time.sleep(2)
    report = {
        "report_id": int(time.time() * 1000),
        "analysis_timestamp_utc": datetime.utcnow().isoformat(),
        "event_summary": "A potential social isolation event was detected.",
        "severity": "Medium",
        "confidence_score": 0.88,
        "suggested_action": "Counselor review is suggested."
    }
    print("Analysis complete.")
    return report

@app.post("/analyze_clip", summary="Upload and analyze a video clip")
async def analyze_clip(file: UploadFile = File(...)):
    temp_dir = "temp_clips"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        analysis_report = run_analysis_model(temp_file_path)
        
        reports_db.append(analysis_report)
        
        return JSONResponse(content=analysis_report)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
        
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.get("/reports", summary="Get all generated incident reports")
async def get_reports():
    return JSONResponse(content={"reports": sorted(reports_db, key=lambda r: r['report_id'], reverse=True)})

if __name__ == "__main__":
    uvicorn.run("analysis_backend:app", host="0.0.0.0", port=8000, reload=True)

