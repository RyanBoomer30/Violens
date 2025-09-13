import fastapi
import uvicorn
import os
import shutil
from datetime import datetime

app = fastapi.FastAPI(
    title="Social Sentinel Analysis API",
    description="Analyzes video clips for bullying and social isolation events.",
    version="1.0.0"
)

TEMP_CLIP_DIR = "temp_clips"

if not os.path.exists(TEMP_CLIP_DIR):
    os.makedirs(TEMP_CLIP_DIR)

def run_analysis_model(clip_path: str) -> dict:
    print(f"🧠 Analyzing clip: {clip_path}... Placeholder model running.")
    
    import time
    time.sleep(2)

    report = {
        "analysis_timestamp_utc": datetime.utcnow().isoformat(),
        "event_type": "Potential Incident Detected",
        "event_summary": "This is a placeholder response from the analysis model. The clip has been received and processed.",
        "severity": "Unknown",
        "confidence_score": 0.95
    }
    
    print("✅ Analysis complete. Returning static report.")
    return report

@app.post("/analyze_clip", summary="Upload and analyze a video clip")
async def analyze_clip_endpoint(file: fastapi.UploadFile = fastapi.File(...)):
    temp_path = os.path.join(TEMP_CLIP_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        analysis_report = run_analysis_model(temp_path)
        
        analysis_report["original_filename"] = file.filename

        return fastapi.responses.JSONResponse(content=analysis_report)

    except Exception as e:
        return fastapi.responses.JSONResponse(
            status_code=500,
            content={"error": "An internal error occurred during analysis.", "detail": str(e)}
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"🧹 Cleaned up temporary file: {temp_path}")

if __name__ == "__main__":
    print("🚀 Starting Social Sentinel Analysis Server at http://127.0.0.1:8000")
    uvicorn.run("analysis_backend:app", host="127.0.0.1", port=8000, reload=True)

