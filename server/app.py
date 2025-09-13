import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import time
import os
import shutil
import json
from datetime import datetime
from video_inference import analyze_video, generate_report

app = FastAPI(title="Social Sentinel Analysis API")

REPORTS_FILE = "reports.json"

def load_reports():
    """Load reports from JSON file"""
    if os.path.exists(REPORTS_FILE):
        try:
            with open(REPORTS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_reports(reports):
    """Save reports to JSON file"""
    try:
        with open(REPORTS_FILE, 'w') as f:
            json.dump(reports, f, indent=2)
    except Exception as e:
        print(f"Error saving reports: {str(e)}")

def add_report(report):
    """Add a new report to the file"""
    reports = load_reports()
    reports.append(report)
    save_reports(reports)

@app.post("/analyze_clip", summary="Upload and analyze a video clip")
async def analyze_clip(file: UploadFile = File(...)):
    # Create directories for temporary processing and permanent storage
    temp_dir = "temp_clips"
    storage_dir = "stored_videos"
    
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)
    
    temp_file_path = os.path.join(temp_dir, file.filename)
    storage_file_path = os.path.join(storage_dir, file.filename)
    
    try:
        # Save uploaded video to temporary location
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Check if video contains violent content
        violence_detected = analyze_video(temp_file_path)
        
        response_data = {
            "filename": file.filename,
            "violence_detected": violence_detected,
            "timestamp": datetime.utcnow().isoformat(),
            "classification": None,
            "report": None
        }
        
        # If violence is detected, generate a detailed report and save video
        if violence_detected.lower() == "true":
            report_data = generate_report(temp_file_path)
            response_data["report"] = report_data
            response_data["classification"] = report_data.get("classification", "Unknown")
            
            # Store the report in the file
            report_entry = {
                "report_id": int(time.time() * 1000),
                "filename": file.filename,
                "analysis_timestamp_utc": datetime.utcnow().isoformat(),
                "violence_detected": True,
                "classification": report_data.get("classification", "Unknown"),
                "detailed_report": report_data.get("detailed_report", ""),
                "report": report_data  # Keep full report for backward compatibility
            }
            add_report(report_entry)
            
            # Save video permanently to storage directory only if violence detected
            shutil.copy2(temp_file_path, storage_file_path)
            response_data["video_saved"] = True
            response_data["storage_path"] = storage_file_path
        else:
            # No violence detected, don't save video
            response_data["video_saved"] = False
            response_data["storage_path"] = None
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.get("/reports", summary="Get all generated incident reports")
async def get_reports():
    reports = load_reports()
    return JSONResponse(content={"reports": sorted(reports, key=lambda r: r['report_id'], reverse=True)})

@app.get("/reports/{report_id}", summary="Get a specific report by ID")
async def get_report(report_id: int):
    reports = load_reports()
    for report in reports:
        if report['report_id'] == report_id:
            return JSONResponse(content=report)
    raise HTTPException(status_code=404, detail="Report not found")

@app.delete("/reports/{report_id}", summary="Delete a specific report by ID")
async def delete_report(report_id: int):
    reports = load_reports()
    original_count = len(reports)
    reports = [r for r in reports if r['report_id'] != report_id]
    
    if len(reports) == original_count:
        raise HTTPException(status_code=404, detail="Report not found")
    
    save_reports(reports)
    return JSONResponse(content={"message": "Report deleted successfully"})

@app.get("/stored_videos", summary="Get list of stored videos")
async def get_stored_videos():
    storage_dir = "stored_videos"
    if not os.path.exists(storage_dir):
        return JSONResponse(content={"videos": []})
    
    videos = []
    for filename in os.listdir(storage_dir):
        file_path = os.path.join(storage_dir, filename)
        if os.path.isfile(file_path):
            stat = os.stat(file_path)
            videos.append({
                "filename": filename,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    return JSONResponse(content={"videos": sorted(videos, key=lambda v: v['created_at'], reverse=True)})

if __name__ == "__main__":
    uvicorn.run("analysis_backend:app", host="0.0.0.0", port=8000, reload=True)

