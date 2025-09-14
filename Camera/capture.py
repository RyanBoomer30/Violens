import cv2
import requests
import time
import os
from datetime import datetime
import tempfile
import numpy as np
import base64

# Configuration
API_BASE_URL = "http://localhost:8000"
INITIAL_RECORDING_DURATION = 1  # seconds for initial recording
PLACEHOLDER_ANALYSIS_DURATION = 0.5  # seconds of footage to send to placeholder model
VIOLENCE_EXTENDED_DURATION = 2  # additional seconds if violence detected
WAIT_DURATION = 300  # seconds between capture attempts
VIDEO_FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480

# Global variables for display
current_status = "Initializing..."
last_analysis = None
recording = False

def draw_overlay(frame, status, analysis=None):
    """Draw minimal status and analysis information on the video frame"""
    overlay = frame.copy()
    
    # Only show analysis results if available
    if analysis:
        violence_detected = analysis.get('violence_detected', 'Unknown')
        
        # Simple status indicator in top-right corner
        if violence_detected == True or (isinstance(violence_detected, str) and violence_detected.lower() == 'true'):
            # Red indicator for violence detected
            cv2.circle(overlay, (VIDEO_WIDTH - 30, 30), 15, (0, 0, 255), -1)
            cv2.putText(overlay, "!", (VIDEO_WIDTH - 35, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        else:
            # Green indicator for no violence
            cv2.circle(overlay, (VIDEO_WIDTH - 30, 30), 15, (0, 255, 0), -1)
    
    # Recording indicator (minimal)
    if recording:
        cv2.circle(overlay, (VIDEO_WIDTH - 30, 70), 8, (0, 0, 255), -1)
    
    # Minimal status text in bottom-left
    cv2.putText(overlay, status, (10, VIDEO_HEIGHT - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return overlay

def extract_half_second_footage(input_video_path):
    """
    Extract half a second of footage from the input video for placeholder analysis.
    """
    try:
        # Create temporary file for half-second video
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_file.close()
        
        # Open input video
        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            print("Error: Could not open input video for half-second extraction")
            return None
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Calculate number of frames for half a second
        frames_for_half_second = int(fps * PLACEHOLDER_ANALYSIS_DURATION)
        
        # Create video writer for half-second clip
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_file.name, fourcc, fps, (width, height))
        
        frame_count = 0
        while frame_count < frames_for_half_second:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
            frame_count += 1
        
        # Release resources
        cap.release()
        out.release()
        
        return temp_file.name
        
    except Exception as e:
        print(f"Error extracting half-second footage: {str(e)}")
        return None

def placeholder_model_analysis(video_path):
    """
    Placeholder model that analyzes half a second of footage for violence.
    This uses the server's analyze_video function with half a second of the captured footage.
    """
    try:
        # Extract half a second of footage
        half_second_video = extract_half_second_footage(video_path)
        if not half_second_video:
            print("Failed to extract half-second footage")
            return False
        
        # Send to server for analysis
        url = f"{API_BASE_URL}/analyze_frame"
        
        with open(half_second_video, 'rb') as video_file:
            files = {'file': (os.path.basename(half_second_video), video_file, 'video/mp4')}
            response = requests.post(url, files=files, timeout=10)
        
        # Clean up half-second video
        cleanup_temp_file(half_second_video)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('violence_detected', False)
        else:
            print(f"Placeholder model error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Placeholder model error: {str(e)}")
        return False

def capture_video_clip_with_display(cap, duration):
    """Capture a video clip from the webcam with live display"""
    global current_status, recording
    
    # Create temporary file for video
    temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    temp_file.close()
    
    # Define codec and create VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_file.name, fourcc, VIDEO_FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))
    
    current_status = f"Recording {duration}s..."
    recording = True
    start_time = time.time()
    
    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if not ret:
            current_status = "Error: Could not read frame from webcam"
            break
        
        # Write frame to video
        out.write(frame)
        
        # Display frame with overlay
        display_frame = draw_overlay(frame, current_status, last_analysis)
        cv2.imshow('Bully Detection System', display_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    recording = False
    current_status = "Processing..."
    
    # Release video writer
    out.release()
    
    return temp_file.name

def send_video_to_server(video_path):
    """Send video to FastAPI server for processing"""
    global current_status, last_analysis
    
    try:
        url = f"{API_BASE_URL}/analyze_clip"
        
        with open(video_path, 'rb') as video_file:
            files = {'file': (os.path.basename(video_path), video_file, 'video/mp4')}
            
            current_status = "Analyzing..."
            # Add timeout to prevent hanging
            response = requests.post(url, files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                current_status = "Ready"
                last_analysis = result
                
                # Print to console as well
                print("Analysis complete!")
                print(f"Violence detected: {result.get('violence_detected', 'Unknown')}")
                
                violence_detected = result.get('violence_detected', False)
                if violence_detected == True or (isinstance(violence_detected, str) and violence_detected.lower() == 'true'):
                    print(f"Classification: {result.get('classification', 'Unknown')}")
                    print(f"Report: {result.get('report', {}).get('detailed_report', 'No report available')}")
                
                return result
            else:
                current_status = f"Error: Server returned status code {response.status_code}"
                print(f"Error: Server returned status code {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
    except requests.exceptions.ConnectionError:
        current_status = "Error: Could not connect to server"
        print("Error: Could not connect to server. Make sure the FastAPI server is running.")
        return None
    except requests.exceptions.Timeout:
        current_status = "Error: Server request timed out"
        print("Error: Server request timed out. The server may be overloaded.")
        return None
    except Exception as e:
        current_status = f"Error: {str(e)}"
        print(f"Error sending video to server: {str(e)}")
        return None

def find_working_camera():
    """Try to find a working camera by testing different indices"""
    print("Searching for available cameras...")
    for i in range(5):  # Try camera indices 0-4
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"Found working camera at index {i}")
                cap.release()
                return i
            cap.release()
    return None

def cleanup_temp_file(file_path):
    """Clean up temporary video file"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        print(f"Warning: Could not delete temporary file {file_path}: {str(e)}")

def main():
    """Main loop for continuous video capture and processing with new logic"""
    global current_status, last_analysis
    
    print("Starting webcam monitoring system with new logic...")
    print("Press 'q' during recording to quit")
    print(f"Initial recording: {INITIAL_RECORDING_DURATION}s, Placeholder analysis: {PLACEHOLDER_ANALYSIS_DURATION}s, Extended if violence: +{VIOLENCE_EXTENDED_DURATION}s")
    print(f"Server URL: {API_BASE_URL}")
    print("-" * 50)
    
    clip_count = 0
    
    # Initialize webcam for continuous display
    print("Initializing webcam...")
    
    # Try to find a working camera
    camera_index = find_working_camera()
    if camera_index is None:
        print("Error: No working camera found")
        print("Possible solutions:")
        print("1. Check if camera is being used by another application")
        print("2. Grant camera permissions to Terminal/Python")
        print("3. Try restarting the application")
        print("4. Check if camera is properly connected")
        return
    
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        print("Possible solutions:")
        print("1. Check if camera is being used by another application")
        print("2. Grant camera permissions to Terminal/Python")
        print("3. Try restarting the application")
        return
    
    # Set video properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, VIDEO_FPS)
    
    # Test webcam by reading a frame
    print("Testing webcam...")
    ret, test_frame = cap.read()
    if not ret:
        print("Error: Could not read from webcam")
        print("This might be due to:")
        print("- Camera permissions not granted")
        print("- Camera being used by another app (FaceTime, Zoom, etc.)")
        print("- Hardware issues")
        cap.release()
        return
    
    print("Webcam initialized successfully")
    print(f"Camera resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"Camera FPS: {cap.get(cv2.CAP_PROP_FPS)}")
    
    try:
        while True:
            clip_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{timestamp}] Cycle #{clip_count}")
            
            # Step 1: Record for 1 second
            print("Step 1: Recording 1 second for footage analysis...")
            video_path = capture_video_clip_with_display(cap, INITIAL_RECORDING_DURATION)
            
            if not video_path:
                print("Failed to capture initial video clip")
                continue
            
            # Step 2: Analyze half a second of footage with placeholder model
            print(f"Step 2: Extracting {PLACEHOLDER_ANALYSIS_DURATION}s and analyzing with placeholder model...")
            
            # Step 3: Analyze half-second footage with placeholder model
            is_violent = placeholder_model_analysis(video_path)
            print(f"Placeholder model result: {'VIOLENT' if is_violent else 'SAFE'}")
            
            if is_violent:
                # Step 4a: If violent, record for 2 more seconds
                print("Step 4a: Violence detected! Recording additional 2 seconds...")
                extended_video_path = capture_video_clip_with_display(cap, VIOLENCE_EXTENDED_DURATION)
                
                if extended_video_path:
                    # Combine the videos or use the extended one
                    # For simplicity, we'll use the extended video
                    cleanup_temp_file(video_path)  # Clean up the initial video
                    video_path = extended_video_path
                    
                    # Step 5: Send to server for full analysis
                    print("Step 5: Sending extended video to server for full analysis...")
                    result = send_video_to_server(video_path)
                    
                    if result:
                        print(f"Video saved: {result.get('video_saved', False)}")
                        if result.get('storage_path'):
                            print(f"Storage path: {result.get('storage_path')}")
                else:
                    print("Failed to capture extended video")
            else:
                # Step 4b: If not violent, just clean up and continue
                print("Step 4b: No violence detected, continuing monitoring...")
            
            # Clean up temporary file
            cleanup_temp_file(video_path)
            
            # Display waiting status
            current_status = "Waiting..."
            print(f"Waiting {WAIT_DURATION} seconds before next cycle...")
            
            # Show live feed during wait period
            wait_start = time.time()
            while time.time() - wait_start < WAIT_DURATION:
                ret, frame = cap.read()
                if not ret:
                    print("Warning: Could not read frame during wait period")
                    time.sleep(0.1)  # Small delay to prevent busy waiting
                    continue
                
                display_frame = draw_overlay(frame, current_status, last_analysis)
                cv2.imshow('Bully Detection System', display_frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("Quit requested by user")
                    break
                elif key == ord('r'):
                    print("Restarting capture cycle...")
                    break
            
    except KeyboardInterrupt:
        print("\nShutting down webcam monitoring system...")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()