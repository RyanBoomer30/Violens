import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import time
import os
import shutil
from datetime import datetime
from video_inference import analyze_video, generate_report

app = FastAPI(title="Social Sentinel Analysis API")

reports_db = []

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
        
        # If violence is detected, generate a detailed report
        if violence_detected.lower() == "true":
            report_data = generate_report(temp_file_path)
            response_data["report"] = report_data
            response_data["classification"] = report_data.get("classification", "Unknown")
            
            # Store the report in the database
            report_entry = {
                "report_id": int(time.time() * 1000),
                "filename": file.filename,
                "analysis_timestamp_utc": datetime.utcnow().isoformat(),
                "violence_detected": True,
                "classification": report_data.get("classification", "Unknown"),
                "detailed_report": report_data.get("detailed_report", ""),
                "report": report_data  # Keep full report for backward compatibility
            }
            reports_db.append(report_entry)
        
        # Save video permanently to storage directory
        shutil.copy2(temp_file_path, storage_file_path)
        response_data["video_saved"] = True
        response_data["storage_path"] = storage_file_path
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.get("/reports", summary="Get all generated incident reports")
async def get_reports():
    return JSONResponse(content={"reports": sorted(reports_db, key=lambda r: r['report_id'], reverse=True)})

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

