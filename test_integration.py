#!/usr/bin/env python3
"""
Test script to verify the integrated bully detection system works correctly.
This script tests the new /capture_and_analyze endpoint.
"""

import requests
import time
import json

def test_server_status():
    """Test if the server is running"""
    try:
        response = requests.get('http://localhost:8000/camera/status')
        if response.status_code == 200:
            status = response.json()
            print(f"✅ Server is running")
            print(f"   Camera active: {status['active']}")
            print(f"   Has camera: {status['has_camera']}")
            return True
        else:
            print(f"❌ Server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Please start the server first:")
        print("   cd server && python app.py")
        return False

def test_camera_start():
    """Test starting the camera"""
    try:
        response = requests.post('http://localhost:8000/camera/start')
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Camera start: {result['message']}")
            return result['active']
        else:
            print(f"❌ Camera start failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error starting camera: {e}")
        return False

def test_capture_and_analyze():
    """Test the new capture_and_analyze endpoint"""
    print("\n🎥 Testing video capture and analysis...")
    print("   This will record a 3-second clip and analyze it...")
    
    try:
        start_time = time.time()
        response = requests.post('http://localhost:8000/capture_and_analyze', timeout=60)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Capture and analysis completed in {end_time - start_time:.1f}s")
            print(f"   Filename: {result['filename']}")
            print(f"   Frames recorded: {result['frames_recorded']}")
            print(f"   Violence detected: {result['violence_detected']}")
            print(f"   Classification: {result.get('classification', 'N/A')}")
            print(f"   Storage type: {result.get('storage_type', 'N/A')}")
            
            if result['violence_detected']:
                print(f"   🚨 VIOLENT INCIDENT DETECTED!")
                if result.get('report', {}).get('detailed_report'):
                    print(f"   Report: {result['report']['detailed_report'][:100]}...")
            else:
                print(f"   ✅ Safe content detected")
                
            return True
        else:
            error_data = response.json() if response.headers.get('content-type') == 'application/json' else {'detail': response.text}
            print(f"❌ Capture failed: {error_data.get('detail', 'Unknown error')}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (this can happen if OpenAI API is slow)")
        return False
    except Exception as e:
        print(f"❌ Error during capture: {e}")
        return False

def main():
    print("🛡️  Testing Integrated Bully Detection System")
    print("=" * 50)
    
    # Test server status
    if not test_server_status():
        return
    
    print()
    
    # Test camera start
    camera_active = test_camera_start()
    if not camera_active:
        print("❌ Cannot proceed without active camera")
        return
    
    print()
    
    # Test capture and analysis
    success = test_capture_and_analyze()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Integration test completed successfully!")
        print("\nNext steps:")
        print("1. Start the React frontend: cd frontend && npm start")
        print("2. Open http://localhost:3000 in your browser")
        print("3. Click 'Start Monitoring' to begin automatic detection")
        print("4. The system will capture 3-second clips every 6 seconds")
        print("5. Watch the live feed for real-time detection results")
    else:
        print("❌ Integration test failed")

if __name__ == "__main__":
    main()
