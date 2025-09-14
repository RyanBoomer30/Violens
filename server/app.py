import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import os
import shutil
import json
import asyncio
import cv2
import threading
import queue
import tempfile
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import List

# Import the new, efficient analysis function
from video_inference import analyze_video_and_generate_report

app = FastAPI(title="Social Sentinel Analysis API")

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "[http://127.0.0.1:3000](http://127.0.0.1:3000)"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Directory Configuration ---
REPORTS_DIR = "reports"
VIOLENT_VIDEOS_DIR = "stored_videos"
NON_VIOLENT_VIDEOS_DIR = "debug_videos"
TEMP_DIR = "temp_clips"


# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # Create a copy of the list to handle disconnections during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# --- Core Video Processing Logic ---
async def process_and_save_video(temp_file_path: str, original_filename: str) -> dict:
    """
    Helper function to analyze a video clip, save it, and generate a report.
    This centralizes the logic used by different endpoints.
    """
    try:
        # Step 1: Analyze the video using the single, efficient function
        analysis_result = analyze_video_and_generate_report(temp_file_path)
        
        violence_detected = analysis_result.get("violence_detected", False)
        
        response_data = {
            "filename": original_filename,
            "timestamp": datetime.utcnow().isoformat(),
            **analysis_result  # Unpack the analysis result into the response
        }

        # Step 2: Create the report entry
        report_entry = {
            "report_id": int(time.time() * 1000),
            "filename": original_filename,
            "analysis_timestamp_utc": datetime.utcnow().isoformat(),
            **analysis_result
        }
        save_report(report_entry, original_filename)

        # Step 3: Move the video file to the appropriate permanent storage
        if violence_detected:
            storage_dir = VIOLENT_VIDEOS_DIR
            storage_type = "violent"
        else:
            storage_dir = NON_VIOLENT_VIDEOS_DIR
            storage_type = "non_violent"
            
        final_storage_path = os.path.join(storage_dir, original_filename)
        shutil.copy2(temp_file_path, final_storage_path)
        
        response_data["video_saved"] = True
        response_data["storage_path"] = final_storage_path
        response_data["storage_type"] = storage_type

        return response_data

    except Exception as e:
        print(f"Error in process_and_save_video: {str(e)}")
        # Re-raise as an HTTPException to be handled by FastAPI
        raise HTTPException(status_code=500, detail=f"Error during video processing: {str(e)}")


# --- API Endpoints ---
@app.post("/analyze_clip", summary="Upload and analyze a video clip")
async def analyze_clip(file: UploadFile = File(...)):
    """
    Endpoint for clients like capture.py to upload a video for full analysis.
    """
    # Use a unique filename to prevent overwrites
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{file.filename}"
    temp_file_path = os.path.join(TEMP_DIR, unique_filename)
    
    try:
        # Save uploaded video to a temporary location
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process the video using the centralized helper function
        result = await process_and_save_video(temp_file_path, unique_filename)
        return JSONResponse(content=result)
        
    except HTTPException as e:
        # Forward HTTP exceptions from the helper
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# --- Report Management ---
def save_report(report: dict, video_filename: str):
    """Saves a report to a JSON file named after the video."""
    base_name = os.path.splitext(video_filename)[0]
    report_path = os.path.join(REPORTS_DIR, f"{base_name}.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=4)
    print(f"Report saved to: {report_path}")

def load_reports() -> List[dict]:
    """Loads all reports from the reports directory."""
    reports = []
    for filename in os.listdir(REPORTS_DIR):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(REPORTS_DIR, filename), 'r') as f:
                    reports.append(json.load(f))
            except Exception as e:
                print(f"Error loading report {filename}: {e}")
    return sorted(reports, key=lambda r: r.get('report_id', 0), reverse=True)

@app.get("/reports", summary="Get all generated incident reports")
async def get_reports():
    return JSONResponse(content={"reports": load_reports()})

# Other endpoints for video lists, specific reports etc. can remain similar
# ... (get_report, delete_report, get_stored_videos etc.)

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print(f"WebSocket connected. Total connections: {len(manager.active_connections)}")
    welcome_message = json.dumps({"type": "connection_established", "message": "Welcome!"})
    await websocket.send_text(welcome_message)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"WebSocket disconnected. Remaining connections: {len(manager.active_connections)}")

# --- Filesystem Watchdog for Real-time Updates ---
class FileUpdateHandler(FileSystemEventHandler):
    def __init__(self, manager: ConnectionManager, loop: asyncio.AbstractEventLoop):
        self.manager = manager
        self.loop = loop

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.json'):
            return

        print(f"📄 New report detected: {event.src_path}")
        try:
            with open(event.src_path, 'r') as f:
                report_data = json.load(f)
            
            message = json.dumps({"type": "new_report", "data": report_data})
            
            # Schedule the broadcast on the main event loop
            asyncio.run_coroutine_threadsafe(self.manager.broadcast(message), self.loop)
        except Exception as e:
            print(f"Error processing new report file {event.src_path}: {e}")

# --- Application Startup and Shutdown ---
observer = Observer()

@app.on_event("startup")
async def on_startup():
    # Create necessary directories on startup
    for path in [REPORTS_DIR, VIOLENT_VIDEOS_DIR, NON_VIOLENT_VIDEOS_DIR, TEMP_DIR]:
        os.makedirs(path, exist_ok=True)
    
    # Start the filesystem observer to push real-time updates to the frontend
    loop = asyncio.get_event_loop()
    event_handler = FileUpdateHandler(manager, loop)
    observer.schedule(event_handler, REPORTS_DIR, recursive=False)
    observer.start()
    print("Filesystem observer started on 'reports' directory.")

@app.on_event("shutdown")
def on_shutdown():
    observer.stop()
    observer.join()
    print("Filesystem observer stopped.")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
