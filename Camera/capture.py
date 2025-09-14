import cv2
import requests
import time
import os
from datetime import datetime
import tempfile
import numpy as np
from collections import deque
import shutil

# Import the model utility from violence_model.py
from violence_model import get_model, CLASSES_LIST, IMAGE_HEIGHT, IMAGE_WIDTH, SEQUENCE_LENGTH

# --- Configuration ---
API_BASE_URL = "http://localhost:8000"
# Assumes app.py is one directory above this script's location
STORAGE_DIR = "server/stored_videos" 
# How many frames to use for the local violence detection model
FRAMES_FOR_ANALYSIS = 16
# How often to run the local model (in seconds)
ANALYSIS_INTERVAL = 1.0 
# The duration of each temporary video clip to record
CLIP_DURATION_SECONDS = 3.0
VIDEO_FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480

# --- Global variables for display ---
current_status = "Initializing..."
last_server_analysis = None


def draw_overlay(frame, status, analysis=None):
    """Draw status and analysis information on the video frame."""
    overlay = frame.copy()
    
    # Display server analysis results if available
    if analysis:
        violence_detected = analysis.get('violence_detected', False)
        classification = analysis.get('classification', 'N/A')
        
        # Simple status indicator in top-right corner
        if violence_detected:
            color = (0, 0, 255) # Red for violence
            cv2.putText(overlay, "!", (VIDEO_WIDTH - 35, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        else:
            color = (0, 255, 0) # Green for safe
        cv2.circle(overlay, (VIDEO_WIDTH - 30, 30), 15, color, -1)
        cv2.putText(overlay, classification, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Display current status text in bottom-left
    cv2.putText(overlay, status, (10, VIDEO_HEIGHT - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return overlay

def send_video_to_server(video_path):
    """Sends video to the FastAPI server and returns the JSON response."""
    global current_status, last_server_analysis
    current_status = "Uploading and analyzing on server..."
    
    try:
        url = f"{API_BASE_URL}/analyze_clip"
        with open(video_path, 'rb') as video_file:
            files = {'file': (os.path.basename(video_path), video_file, 'video/mp4')}
            response = requests.post(url, files=files, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                print("Server analysis complete:")
                print(f"  - Violence Detected: {result.get('violence_detected')}")
                print(f"  - Classification: {result.get('classification')}")
                last_server_analysis = result
                return result
            else:
                print(f"Error: Server returned status code {response.status_code}")
                print(f"Response: {response.text}")
                current_status = f"Error: Server responded with {response.status_code}"
                return None
                
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to server: {e}")
        current_status = "Error: Cannot connect to server"
        return None

def find_working_camera():
    """Tries to find a working camera by testing different indices."""
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                cap.release()
                print(f"Found working camera at index {i}")
                return i
            cap.release()
    return None

def main():
    """Main loop for continuous block-based recording and analysis."""
    global current_status
    
    # --- Initialization ---
    camera_index = find_working_camera()
    if camera_index is None:
        print("Error: No working camera found. Exiting.")
        return
        
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
        
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, VIDEO_FPS)

    # Ensure the storage directory exists
    os.makedirs(STORAGE_DIR, exist_ok=True)
    print(f"Storing detected videos in: {os.path.abspath(STORAGE_DIR)}")
    
    print("Webcam initialized.")
    print("Loading local violence detection model...")
    model = get_model()
    print("Model loaded. Starting monitoring...")
    print("Press 'q' to quit.")
    
    # --- Main Loop ---
    clip_count = 0
    video_path = None
    out = None

    try:
        while True:
            clip_count += 1
            print(f"\n--- Starting to record clip #{clip_count} ({CLIP_DURATION_SECONDS}s) ---")

            # Create a new temporary file for each clip
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                video_path = temp_file.name
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(video_path, fourcc, VIDEO_FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))

            violence_detected_in_clip = False
            last_analysis_time = time.time()
            start_time = time.time()
            
            frames_for_analysis = deque(maxlen=FRAMES_FOR_ANALYSIS)
            current_status = f"Recording clip #{clip_count}..."

            # Record frames for the specified duration
            while time.time() - start_time < CLIP_DURATION_SECONDS:
                ret, frame = cap.read()
                if not ret:
                    print("Error: Could not read frame.")
                    break
                
                out.write(frame)
                frames_for_analysis.append(frame) # Add to deque for local analysis

                # Periodically run the local model on the most recent frames
                if not violence_detected_in_clip and time.time() - last_analysis_time > ANALYSIS_INTERVAL:
                    last_analysis_time = time.time()
                    if len(frames_for_analysis) >= FRAMES_FOR_ANALYSIS:
                        
                        processed_frames = []
                        for f in frames_for_analysis:
                            resized = cv2.resize(f, (IMAGE_HEIGHT, IMAGE_WIDTH))
                            normalized = resized / 255.0
                            processed_frames.append(normalized)
                        
                        prediction_input = np.expand_dims(processed_frames, axis=0)
                        probabilities = model.predict(prediction_input, verbose=0)[0]
                        predicted_label_index = np.argmax(probabilities)
                        predicted_class = CLASSES_LIST[predicted_label_index]
                        
                        if predicted_class == "Violence":
                            print(f"!!! Violence detected in clip #{clip_count} (Confidence: {probabilities[predicted_label_index]:.2f}) !!!")
                            violence_detected_in_clip = True
                            current_status = "Violence detected! Finishing clip..."
                
                # Update display
                display_frame = draw_overlay(frame, current_status, last_server_analysis)
                cv2.imshow('Social Sentinel Monitoring', display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    raise SystemExit("User requested quit.")

            # --- Post-Recording Action ---
            out.release()
            out = None # Explicitly release the object
            
            if violence_detected_in_clip:
                print(f"Clip #{clip_count} finished. Storing and sending to server...")
                
                # Give the OS a moment to finish writing the file before we access it
                time.sleep(2.0)

                # Create a permanent filename and path
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                permanent_filename = f"capture_{timestamp}_clip{clip_count}.mp4"
                destination_path = os.path.join(STORAGE_DIR, permanent_filename)

                # Copy the temporary file to the permanent storage directory
                try:
                    shutil.copyfile(video_path, destination_path)
                    
                    # Add a check for file size to confirm it was written correctly
                    file_size = os.path.getsize(destination_path)
                    print(f"Successfully saved video to {destination_path} ({file_size} bytes)")
                    
                    if file_size > 0:
                        # Send the NEWLY CREATED permanent file to the server
                        send_video_to_server(destination_path)
                    else:
                        print(f"Error: Copied file is empty at {destination_path}. Not sending.")

                except Exception as e:
                    print(f"Error saving or sending video file: {e}")

            else:
                print(f"Clip #{clip_count} finished. No violence detected. Discarding.")
                current_status = "Monitoring..."

            # Clean up the temporary video file
            if os.path.exists(video_path):
                os.unlink(video_path)
            video_path = None

    except (SystemExit, KeyboardInterrupt) as e:
        print(f"\n{e} Shutting down...")
    finally:
        if out and out.isOpened():
            out.release()
        if video_path and os.path.exists(video_path):
            os.unlink(video_path)
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

