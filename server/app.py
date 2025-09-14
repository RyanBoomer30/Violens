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
from video_inference import analyze_video, generate_report
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import List

app = FastAPI(title="Social Sentinel Analysis API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPORTS_DIR = "debug_videos/reports"

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove stale connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Camera streaming setup
camera_frame_queue = queue.Queue(maxsize=10)
camera_active = False
camera_thread = None

def find_working_camera():
    """Try to find a working camera by testing different indices"""
    for i in range(5):  # Try camera indices 0-4
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                cap.release()
                return i
            cap.release()
    return None

def camera_capture_thread():
    """Background thread to capture frames from camera"""
    global camera_active
    
    camera_index = find_working_camera()
    if camera_index is None:
        print("No working camera found for streaming")
        return
    
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    print(f"Started camera streaming thread with camera index {camera_index}")
    frame_count = 0
    
    while camera_active:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from camera")
            continue
            
        frame_count += 1
        if frame_count % 30 == 0:  # Log every 30 frames (about 1 second at 30fps)
            print(f"Captured {frame_count} frames, queue size: {camera_frame_queue.qsize()}")
            
        # Encode frame as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_bytes = buffer.tobytes()
        
        # Put frame in queue (non-blocking)
        try:
            camera_frame_queue.put_nowait(frame_bytes)
        except queue.Full:
            # Remove oldest frame and add new one
            try:
                camera_frame_queue.get_nowait()
                camera_frame_queue.put_nowait(frame_bytes)
            except queue.Empty:
                pass
    
    cap.release()
    print(f"Camera streaming thread stopped after {frame_count} frames")

def start_camera_streaming():
    """Start the camera streaming thread"""
    global camera_active, camera_thread
    
    if not camera_active:
        camera_active = True
        camera_thread = threading.Thread(target=camera_capture_thread, daemon=True)
        camera_thread.start()
        print("Camera streaming started")
        return True
    return False

def stop_camera_streaming():
    """Stop the camera streaming thread"""
    global camera_active, camera_thread
    
    if camera_active:
        camera_active = False
        if camera_thread:
            camera_thread.join(timeout=5)
        print("Camera streaming stopped")
        return True
    return False

def generate_video_stream():
    """Generator function for video streaming"""
    frame_sent_count = 0
    while True:
        try:
            # Get frame from queue (blocking with timeout)
            frame_bytes = camera_frame_queue.get(timeout=1.0)
            frame_sent_count += 1
            if frame_sent_count % 30 == 0:  # Log every 30 frames
                print(f"Sent {frame_sent_count} frames to client, queue size: {camera_frame_queue.qsize()}")
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except queue.Empty:
            # Send a placeholder frame or continue
            print("Video stream: No frames available in queue")
            continue
        except Exception as e:
            print(f"Error in video stream: {e}")
            break

# File system event handler for stored_videos directory
class StoredVideoHandler(FileSystemEventHandler):
    def __init__(self, connection_manager, loop=None):
        self.connection_manager = connection_manager
        self.loop = loop

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            filename = os.path.basename(event.src_path)
            print(f"🚨 NEW VIOLENT VIDEO DETECTED: {filename}")
            message = json.dumps({
                "type": "new_violent_video",
                "filename": filename,
                "timestamp": datetime.utcnow().isoformat(),
                "path": event.src_path
            })
            # Use asyncio.run_coroutine_threadsafe to schedule from thread
            try:
                if self.loop and not self.loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(
                        self.connection_manager.broadcast(message), 
                        self.loop
                    )
                    print(f"Scheduled broadcast for {filename}")
                else:
                    print("No event loop available for broadcasting")
            except Exception as e:
                print(f"Error broadcasting message: {e}")

# File system event handler for reports directory
class ReportsHandler(FileSystemEventHandler):
    def __init__(self, connection_manager, loop=None):
        self.connection_manager = connection_manager
        self.loop = loop

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            filename = os.path.basename(event.src_path)
            print(f"📄 NEW REPORT GENERATED: {filename}")
            
            # Try to read the report data
            try:
                with open(event.src_path, 'r') as f:
                    report_data = json.load(f)
                
                message = json.dumps({
                    "type": "new_report",
                    "filename": filename,
                    "report_id": report_data.get("report_id"),
                    "video_filename": report_data.get("filename"),
                    "violence_detected": report_data.get("violence_detected", False),
                    "classification": report_data.get("classification", "Unknown"),
                    "timestamp": datetime.utcnow().isoformat(),
                    "path": event.src_path
                })
                
                # Use asyncio.run_coroutine_threadsafe to schedule from thread
                try:
                    if self.loop and not self.loop.is_closed():
                        future = asyncio.run_coroutine_threadsafe(
                            self.connection_manager.broadcast(message), 
                            self.loop
                        )
                        print(f"Scheduled report broadcast for {filename}")
                    else:
                        print("No event loop available for broadcasting")
                except Exception as e:
                    print(f"Error broadcasting report message: {e}")
                    
            except Exception as e:
                print(f"Error reading report file {filename}: {e}")

# Initialize file observers
stored_videos_dir = "stored_videos"
if not os.path.exists(stored_videos_dir):
    os.makedirs(stored_videos_dir)

reports_dir = "debug_videos/reports"
if not os.path.exists(reports_dir):
    os.makedirs(reports_dir)

# Global variables for observers (will be initialized in main)
video_observer = None
video_event_handler = None
reports_observer = None
reports_event_handler = None

def load_reports():
    """Load all reports from individual JSON files"""
    reports = []
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
        return reports
    
    for filename in os.listdir(REPORTS_DIR):
        if filename.endswith('.json'):
            file_path = os.path.join(REPORTS_DIR, filename)
            try:
                with open(file_path, 'r') as f:
                    report = json.load(f)
                    reports.append(report)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error loading report {filename}: {str(e)}")
    return reports

def save_report(report, video_filename):
    """Save individual report to JSON file with same name as video"""
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
    
    # Extract filename without extension and add .json
    base_name = os.path.splitext(video_filename)[0]
    report_filename = f"{base_name}.json"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    
    try:
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {report_path}")
    except Exception as e:
        print(f"Error saving report {report_filename}: {str(e)}")

def delete_report_file(report_id):
    """Delete individual report file by report_id"""
    if not os.path.exists(REPORTS_DIR):
        return False
    
    for filename in os.listdir(REPORTS_DIR):
        if filename.endswith('.json'):
            file_path = os.path.join(REPORTS_DIR, filename)
            try:
                with open(file_path, 'r') as f:
                    report = json.load(f)
                    if report.get('report_id') == report_id:
                        os.remove(file_path)
                        print(f"Deleted report file: {filename}")
                        return True
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Error reading report {filename}: {str(e)}")
    return False

@app.post("/analyze_frame", summary="Analyze footage for violence (placeholder model)")
async def analyze_frame(file: UploadFile = File(...)):
    """Analyze footage for violence using the existing analyze_video function"""
    try:
        # Create temporary file for processing
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_file_path = temp_file.name
        temp_file.close()
        
        # Save uploaded file
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Use existing analyze_video function
        violence_detected = analyze_video(temp_file_path)
        
        # Clean up temporary file
        try:
            os.unlink(temp_file_path)
        except Exception as e:
            print(f"Warning: Could not delete temporary file {temp_file_path}: {str(e)}")
        
        return JSONResponse(content={
            "violence_detected": violence_detected,
            "message": "Footage analysis complete"
        })
        
    except Exception as e:
        print(f"Error in analyze_frame: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error analyzing footage: {str(e)}"}
        )

@app.post("/analyze_clip", summary="Upload and analyze a video clip")
async def analyze_clip(file: UploadFile = File(...)):
    # Create directories for temporary processing and permanent storage
    temp_dir = "temp_clips"
    violent_videos_dir = "stored_videos"
    non_violent_videos_dir = "debug_videos"
    
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    if not os.path.exists(violent_videos_dir):
        os.makedirs(violent_videos_dir)
    if not os.path.exists(non_violent_videos_dir):
        os.makedirs(non_violent_videos_dir)
    
    temp_file_path = os.path.join(temp_dir, file.filename)
    violent_storage_path = os.path.join(violent_videos_dir, file.filename)
    non_violent_storage_path = os.path.join(non_violent_videos_dir, file.filename)
    
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
        
        print("Violence status: " + str(violence_detected))
        
        # If violence is detected, generate a detailed report and save video
        if violence_detected:
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
            save_report(report_entry, file.filename)
            
            # Save video permanently to violent videos directory
            shutil.copy2(temp_file_path, violent_storage_path)
            response_data["video_saved"] = True
            response_data["storage_path"] = violent_storage_path
            response_data["storage_type"] = "violent"
        else:
            # No violence detected, save to debug folder for debugging purposes
            shutil.copy2(temp_file_path, non_violent_storage_path)

            report_data = generate_report(temp_file_path)
            response_data["report"] = report_data

            report_entry = {
                "report_id": int(time.time() * 1000),
                "filename": file.filename,
                "analysis_timestamp_utc": datetime.utcnow().isoformat(),
                "violence_detected": False,
                "classification": report_data.get("classification", "Unknown"),
                "detailed_report": report_data.get("detailed_report", ""),
                "report": report_data  # Keep full report for backward compatibility
            }

            save_report(report_entry, file.filename)

            # Actual code
            # report_data = generate_report(temp_file_path)
            # response_data["report"] = report_data
            response_data["video_saved"] = True
            response_data["storage_path"] = non_violent_storage_path
            response_data["storage_type"] = "non_violent"
        

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
    if delete_report_file(report_id):
        return JSONResponse(content={"message": "Report deleted successfully"})
    else:
        raise HTTPException(status_code=404, detail="Report not found")

@app.get("/stored_videos", summary="Get list of violent videos")
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
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": "violent"
            })
    
    return JSONResponse(content={"videos": sorted(videos, key=lambda v: v['created_at'], reverse=True)})

@app.get("/debug_videos", summary="Get list of non-violent debug videos")
async def get_debug_videos():
    storage_dir = "debug_videos"
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
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": "non_violent"
            })
    
    return JSONResponse(content={"videos": sorted(videos, key=lambda v: v['created_at'], reverse=True)})

@app.get("/video_stream", summary="Live camera video stream")
async def video_stream():
    """Endpoint for live camera video streaming"""
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/camera/start", summary="Start camera streaming")
async def start_camera():
    """Start the camera streaming"""
    success = start_camera_streaming()
    if success:
        return JSONResponse(content={"message": "Camera streaming started", "active": True})
    else:
        return JSONResponse(content={"message": "Camera streaming already active", "active": True})

@app.post("/camera/stop", summary="Stop camera streaming")
async def stop_camera():
    """Stop the camera streaming"""
    success = stop_camera_streaming()
    if success:
        return JSONResponse(content={"message": "Camera streaming stopped", "active": False})
    else:
        return JSONResponse(content={"message": "Camera streaming already stopped", "active": False})

@app.get("/camera/status", summary="Get camera status")
async def camera_status():
    """Get current camera streaming status"""
    return JSONResponse(content={
        "active": camera_active,
        "has_camera": find_working_camera() is not None
    })

@app.post("/capture_and_analyze", summary="Capture video clip from camera and analyze it")
async def capture_and_analyze():
    """Capture a 3-second video clip from the active camera and analyze it for violence"""
    global camera_active
    
    if not camera_active:
        raise HTTPException(status_code=400, detail="Camera streaming is not active")
    
    camera_index = find_working_camera()
    if camera_index is None:
        raise HTTPException(status_code=500, detail="No working camera found")
    
    # Create temporary file for video
    temp_dir = "temp_clips"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    temp_filename = f"frontend_clip_{timestamp}.mp4"
    temp_file_path = os.path.join(temp_dir, temp_filename)
    
    try:
        # Open camera for recording
        cap = cv2.VideoCapture(camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail="Could not open camera for recording")
        
        # Define codec and create VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_file_path, fourcc, 30.0, (640, 480))
        
        # Record for 3 seconds
        start_time = time.time()
        frames_recorded = 0
        
        while time.time() - start_time < 3.0:
            ret, frame = cap.read()
            if not ret:
                break
            
            out.write(frame)
            frames_recorded += 1
        
        # Release resources
        out.release()
        cap.release()
        
        if frames_recorded == 0:
            raise HTTPException(status_code=500, detail="No frames were recorded")
        
        print(f"Recorded {frames_recorded} frames to {temp_file_path}")
        
        # Analyze the recorded video
        violence_detected = analyze_video(temp_file_path)
        
        response_data = {
            "filename": temp_filename,
            "violence_detected": violence_detected,
            "timestamp": datetime.utcnow().isoformat(),
            "frames_recorded": frames_recorded,
            "classification": None,
            "report": None
        }
        
        # Storage directories
        violent_videos_dir = "stored_videos"
        non_violent_videos_dir = "debug_videos"
        
        if not os.path.exists(violent_videos_dir):
            os.makedirs(violent_videos_dir)
        if not os.path.exists(non_violent_videos_dir):
            os.makedirs(non_violent_videos_dir)
        
        # If violence is detected, generate a detailed report and save video
        if violence_detected:
            report_data = generate_report(temp_file_path)
            response_data["report"] = report_data
            response_data["classification"] = report_data.get("classification", "Unknown")
            
            # Store the report
            report_entry = {
                "report_id": int(time.time() * 1000),
                "filename": temp_filename,
                "analysis_timestamp_utc": datetime.utcnow().isoformat(),
                "violence_detected": True,
                "classification": report_data.get("classification", "Unknown"),
                "detailed_report": report_data.get("detailed_report", ""),
                "report": report_data
            }
            save_report(report_entry, temp_filename)
            
            # Save video permanently to violent videos directory
            violent_storage_path = os.path.join(violent_videos_dir, temp_filename)
            shutil.copy2(temp_file_path, violent_storage_path)
            response_data["video_saved"] = True
            response_data["storage_path"] = violent_storage_path
            response_data["storage_type"] = "violent"
        else:
            # No violence detected, save to debug folder
            non_violent_storage_path = os.path.join(non_violent_videos_dir, temp_filename)
            shutil.copy2(temp_file_path, non_violent_storage_path)
            
            # Generate report for non-violent content too
            report_data = generate_report(temp_file_path)
            response_data["report"] = report_data
            response_data["classification"] = report_data.get("classification", "Safe")
            
            report_entry = {
                "report_id": int(time.time() * 1000),
                "filename": temp_filename,
                "analysis_timestamp_utc": datetime.utcnow().isoformat(),
                "violence_detected": False,
                "classification": report_data.get("classification", "Safe"),
                "detailed_report": report_data.get("detailed_report", ""),
                "report": report_data
            }
            save_report(report_entry, temp_filename)
            
            response_data["video_saved"] = True
            response_data["storage_path"] = non_violent_storage_path
            response_data["storage_type"] = "non_violent"
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        print(f"Error in capture_and_analyze: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                print(f"Warning: Could not delete temporary file {temp_file_path}: {str(e)}")

@app.get("/video/{filename}", summary="Serve video files")
async def serve_video(filename: str):
    """Serve video files from stored_videos directory"""
    video_path = os.path.join("stored_videos", filename)
    
    # Check if file exists
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Return the video file
    return FileResponse(
        path=video_path,
        media_type='video/mp4',
        filename=filename
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("WebSocket connection attempt")
    await manager.connect(websocket)
    print(f"WebSocket connected. Total connections: {len(manager.active_connections)}")
    
    # Send a welcome message to confirm connection
    welcome_message = json.dumps({
        "type": "connection_established",
        "message": "WebSocket connected successfully",
        "timestamp": datetime.utcnow().isoformat()
    })
    await manager.send_personal_message(welcome_message, websocket)
    
    try:
        while True:
            # Keep the connection alive by waiting for messages
            data = await websocket.receive_text()
            print(f"Received WebSocket message: {data}")
            # Echo back any messages (optional)
            await manager.send_personal_message(f"Message received: {data}", websocket)
    except WebSocketDisconnect:
        print("WebSocket disconnected")
        manager.disconnect(websocket)
        print(f"WebSocket disconnected. Remaining connections: {len(manager.active_connections)}")

async def startup():
    """Initialize the file observers with the current event loop"""
    global video_observer, video_event_handler, reports_observer, reports_event_handler
    
    loop = asyncio.get_event_loop()
    
    # Initialize video observer for stored_videos directory
    video_observer = Observer()
    video_event_handler = StoredVideoHandler(manager, loop)
    video_observer.schedule(video_event_handler, stored_videos_dir, recursive=False)
    video_observer.start()
    print("Video file observer started")
    
    # Initialize reports observer for reports directory
    reports_observer = Observer()
    reports_event_handler = ReportsHandler(manager, loop)
    reports_observer.schedule(reports_event_handler, reports_dir, recursive=False)
    reports_observer.start()
    print("Reports file observer started")
    
    # Note: Camera streaming will be started manually via API calls

def shutdown():
    """Clean up the file observers and camera streaming"""
    global video_observer, reports_observer
    
    # Stop camera streaming
    stop_camera_streaming()
    
    if video_observer:
        video_observer.stop()
        video_observer.join()
        print("Video file observer stopped")
        
    if reports_observer:
        reports_observer.stop()
        reports_observer.join()
        print("Reports file observer stopped")

# Add startup and shutdown events
@app.on_event("startup")
async def on_startup():
    await startup()

@app.on_event("shutdown")
def on_shutdown():
    shutdown()

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

