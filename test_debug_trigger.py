#!/usr/bin/env python3
"""
Test script to demonstrate the debug video trigger functionality.
This script creates a test video file in the debug_videos directory to trigger the notification.
"""

import os
import shutil
import time
from datetime import datetime

def create_test_video():
    """Create a test video file in debug_videos directory"""
    
    # Ensure debug_videos directory exists
    debug_dir = "server/debug_videos"
    if not os.path.exists(debug_dir):
        os.makedirs(debug_dir)
        print(f"Created directory: {debug_dir}")
    
    # Check if test video exists in server/output
    source_video = "server/output/test.mp4"
    if not os.path.exists(source_video):
        # Try alternative location
        source_video = "server/output/fi005.mp4"
        if not os.path.exists(source_video):
            print(f"Error: No test video found in server/output/")
            print("Please ensure you have a video file in server/output/ directory")
            return False
    
    # Create unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_filename = f"debug_test_{timestamp}.mp4"
    dest_path = os.path.join(debug_dir, dest_filename)
    
    print(f"Copying {source_video} to {dest_path}")
    
    # Copy the test video to debug_videos directory
    shutil.copy2(source_video, dest_path)
    
    print(f"✅ Test video created: {dest_filename}")
    print("🎬 This should trigger a notification in the frontend!")
    print("📝 Check the browser console for the print output")
    
    return True

if __name__ == "__main__":
    print("🧪 Debug Video Trigger Test")
    print("=" * 40)
    
    if create_test_video():
        print("\n✨ Test completed successfully!")
        print("\nTo see the trigger in action:")
        print("1. Start the FastAPI server: cd server && python app.py")
        print("2. Start the React frontend: cd frontend && npm start")
        print("3. Run this test script again: python test_debug_trigger.py")
        print("4. Check the browser console for the print output!")
    else:
        print("\n❌ Test failed - check the error messages above")
