# Debug Video Trigger API Documentation

## Overview

This feature adds real-time notifications when new videos are saved to the `debug_videos` directory. When a new video file is detected, it triggers a print function in the frontend console and displays a visual notification in the UI.

## How It Works

1. **File System Monitoring**: The FastAPI server monitors the `debug_videos` directory using the `watchdog` library
2. **WebSocket Communication**: Real-time notifications are sent to the frontend via WebSocket connection
3. **Frontend Notifications**: The React frontend receives notifications and triggers both console logging and UI updates

## Setup Instructions

### 1. Install Backend Dependencies

```bash
cd server
pip install -r requirements.txt
```

The new dependencies added:
- `websockets`: For WebSocket communication
- `watchdog`: For file system monitoring

### 2. Start the Backend Server

```bash
cd server
python app.py
```

The server will:
- Start the FastAPI application on `http://localhost:8000`
- Begin monitoring the `debug_videos` directory
- Accept WebSocket connections at `ws://localhost:8000/ws`

### 3. Start the Frontend

```bash
cd frontend
npm install  # if not already done
npm start
```

The frontend will:
- Connect to the WebSocket server automatically
- Display connection status in the "Debug Video Notifications" panel
- Show real-time notifications when new videos are detected

## Testing the Feature

### Method 1: Use the Test Script

```bash
python test_trigger.py
```

This script will:
- Copy a test video from `server/output/test.mp4` to `debug_videos/`
- Trigger the notification system
- Display instructions for viewing the results

### Method 2: Manual Testing

1. Ensure both backend and frontend are running
2. Copy any video file (`.mp4`, `.avi`, `.mov`, `.mkv`) to the `server/debug_videos/` directory
3. Watch the frontend for notifications

## What Happens When a Video is Detected

### Console Output (Print Function)
When a new video is saved to `debug_videos`, the frontend console will display:

```
🎬 NEW DEBUG VIDEO DETECTED!
Filename: debug_test_20240914_143022.mp4
Timestamp: 2024-09-14T21:30:22.123Z
Path: /path/to/debug_videos/debug_test_20240914_143022.mp4
-----------------------------------
```

### UI Notifications
- A new notification appears in the "Debug Video Notifications" panel
- Shows the video filename and timestamp
- Includes a visual animation when new notifications arrive
- WebSocket connection status is displayed (Connected/Disconnected)

## API Endpoints

### WebSocket Endpoint
- **URL**: `ws://localhost:8000/ws`
- **Purpose**: Real-time communication for debug video notifications
- **Message Format**:
  ```json
  {
    "type": "new_debug_video",
    "filename": "debug_test_20240914_143022.mp4",
    "timestamp": "2024-09-14T21:30:22.123456",
    "path": "/full/path/to/video.mp4"
  }
  ```

### Existing HTTP Endpoints
All existing endpoints remain unchanged:
- `POST /analyze_clip` - Upload and analyze video clips
- `GET /reports` - Get all incident reports
- `GET /debug_videos` - Get list of non-violent debug videos
- And others...

## File Structure

```
BullyDetectionSystem/
├── server/
│   ├── app.py                 # Updated with WebSocket and file monitoring
│   ├── debug_videos/          # Monitored directory
│   ├── requirements.txt       # Updated with new dependencies
│   └── ...
├── frontend/
│   └── src/
│       ├── App.js            # Updated with WebSocket client
│       ├── App.css           # Updated with notification styles
│       └── ...
├── test_trigger.py           # Test script for triggering notifications
└── DEBUG_VIDEO_TRIGGER_README.md
```

## Troubleshooting

### WebSocket Connection Issues
- Ensure the backend server is running on port 8000
- Check browser console for connection errors
- Verify firewall settings allow WebSocket connections

### File Monitoring Not Working
- Ensure the `debug_videos` directory exists (created automatically)
- Check that video files have supported extensions (`.mp4`, `.avi`, `.mov`, `.mkv`)
- Verify the `watchdog` library is properly installed

### Frontend Not Receiving Notifications
- Check the WebSocket connection status in the UI
- Look for JavaScript errors in the browser console
- Ensure both frontend and backend are running

## Technical Details

### Backend Changes
- Added `ConnectionManager` class for WebSocket management
- Added `DebugVideoHandler` class for file system events
- Integrated file observer with FastAPI lifecycle
- Added WebSocket endpoint at `/ws`

### Frontend Changes
- Added WebSocket client connection with auto-reconnect
- Added debug video notifications state management
- Added visual notification component with animations
- Added console logging for debug video events

### Dependencies Added
- **Backend**: `websockets`, `watchdog`
- **Frontend**: No new dependencies (uses native WebSocket API)

## Future Enhancements

Potential improvements for this feature:
- Add notification persistence (save to database)
- Add email/SMS notifications for important events
- Add filtering options for different video types
- Add batch processing notifications
- Add notification acknowledgment system
