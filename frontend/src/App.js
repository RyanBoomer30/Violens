import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [detectionData, setDetectionData] = useState([]);
  const [alertCount, setAlertCount] = useState(0);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [violentVideoNotifications, setViolentVideoNotifications] = useState([]);
  const [reportNotifications, setReportNotifications] = useState([]);
  const [wsConnection, setWsConnection] = useState(null);
  const [violentIncidentData, setViolentIncidentData] = useState([]);
  const [cameraStatus, setCameraStatus] = useState({ active: false, has_camera: false });
  const [cameraError, setCameraError] = useState(null);
  const [analysisStatus, setAnalysisStatus] = useState('Waiting...');
  const [isRecording, setIsRecording] = useState(false);
  const [lastAnalysisResult, setLastAnalysisResult] = useState(null);
  const [clipCount, setClipCount] = useState(0);

  // WebSocket connection for real-time notifications
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8000/ws');
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnection(ws);
      };
      
      ws.onmessage = (event) => {
        console.log('WebSocket message received:', event.data);
        try {
          const data = JSON.parse(event.data);
          console.log('Parsed WebSocket data:', data);
          
          if (data.type === 'connection_established') {
            console.log('✅ WebSocket connection established:', data.message);
          } else if (data.type === 'new_violent_video') {
            // Print function triggered when new video is saved to stored_videos
            console.log('🚨 NEW VIOLENT VIDEO DETECTED!');
            console.log(`Filename: ${data.filename}`);
            console.log(`Timestamp: ${data.timestamp}`);
            console.log(`Path: ${data.path}`);
            console.log('-----------------------------------');
            
            // Add to notifications state for UI display
            const notification = {
              id: Date.now(),
              filename: data.filename,
              filePath: data.path,
              timestamp: new Date(data.timestamp).toLocaleTimeString(),
              message: `🚨 VIOLENT INCIDENT DETECTED: ${data.filename}`
            };
            
            setViolentVideoNotifications(prev => [notification, ...prev.slice(0, 4)]);
            
            // Update Detection Confidence graph data with high confidence for violent incidents
            const incidentTime = new Date(data.timestamp);
            const timeLabel = incidentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            const detectionEntry = {
              timestamp: timeLabel,
              confidence: 95, // High confidence for confirmed violent incidents
              location: 'Camera 1',
              severity: 'High'
            };
            
            setDetectionData(prev => [...prev.slice(-9), detectionEntry]);
            setAlertCount(prev => prev + 1);
            
            // Update violent incident graph data
            setViolentIncidentData(prev => {
              const existingIndex = prev.findIndex(item => item.timeLabel === timeLabel);
              
              if (existingIndex >= 0) {
                // Increment count for existing time interval
                const updated = [...prev];
                updated[existingIndex] = {
                  ...updated[existingIndex],
                  count: updated[existingIndex].count + 1
                };
                return updated;
              } else {
                // Add new time interval
                const newEntry = {
                  timeLabel,
                  count: 1,
                  timestamp: incidentTime
                };
                
                // Keep only last 10 time intervals and sort by timestamp
                const updated = [...prev, newEntry]
                  .sort((a, b) => a.timestamp - b.timestamp)
                  .slice(-10);
                
                return updated;
              }
            });
          } else if (data.type === 'new_report') {
            // Print function triggered when new report is generated
            console.log('📄 NEW REPORT GENERATED!');
            console.log(`Report ID: ${data.report_id}`);
            console.log(`Video: ${data.video_filename}`);
            console.log(`Violence Detected: ${data.violence_detected}`);
            console.log(`Classification: ${data.classification}`);
            console.log('-----------------------------------');
            
            // Add to report notifications state for UI display
            const reportNotification = {
              id: Date.now(),
              reportId: data.report_id,
              filename: data.filename,
              videoFilename: data.video_filename,
              violenceDetected: data.violence_detected,
              classification: data.classification,
              timestamp: new Date(data.timestamp).toLocaleTimeString(),
              message: data.violence_detected 
                ? `🚨 INCIDENT REPORT: ${data.classification}` 
                : `📊 ANALYSIS COMPLETE: ${data.video_filename}`
            };
            
            setReportNotifications(prev => [reportNotification, ...prev.slice(0, 4)]);
          } else {
            console.log('Unknown WebSocket message type:', data.type);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
          console.error('Raw message was:', event.data);
        }
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnection(null);
        // Attempt to reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };
    
    connectWebSocket();
    
    return () => {
      if (wsConnection) {
        wsConnection.close();
      }
    };
  }, []);

  // Video capture and analysis functionality
  const captureVideoClip = async () => {
    if (!cameraStatus.active || !isMonitoring) {
      console.log('Camera not active or monitoring disabled');
      return;
    }

    try {
      setIsRecording(true);
      setAnalysisStatus('Recording...');
      
      // Use the server endpoint to capture and analyze video directly from the camera
      const response = await fetch('http://localhost:8000/capture_and_analyze', {
        method: 'POST'
      });
      
      if (response.ok) {
        const result = await response.json();
        setLastAnalysisResult(result);
        setAnalysisStatus('Ready');
        
        console.log('Analysis complete:', result);
        console.log(`Violence detected: ${result.violence_detected}`);
        console.log(`Frames recorded: ${result.frames_recorded}`);
        
        if (result.violence_detected) {
          console.log(`Classification: ${result.classification}`);
          console.log(`Report: ${result.report?.detailed_report}`);
        }
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('Analysis failed:', errorData.detail);
        setAnalysisStatus(`Error: ${errorData.detail}`);
      }
      
    } catch (error) {
      console.error('Error capturing video:', error);
      setAnalysisStatus('Error: Network issue');
    } finally {
      setIsRecording(false);
    }
  };

  // Automatic video capture loop (similar to capture.py)
  useEffect(() => {
    let captureInterval;
    
    if (isMonitoring && cameraStatus.active) {
      console.log('Starting automatic video capture every 6 seconds (3s recording + 3s wait)');
      setAnalysisStatus('Waiting...');
      
      // Initial capture after 1 second
      const initialTimeout = setTimeout(() => {
        captureVideoClip();
        setClipCount(prev => prev + 1);
      }, 1000);
      
      // Then capture every 6 seconds (3s recording + 3s processing/waiting)
      captureInterval = setInterval(() => {
        captureVideoClip();
        setClipCount(prev => prev + 1);
      }, 6000);
      
      return () => {
        clearTimeout(initialTimeout);
        clearInterval(captureInterval);
      };
    } else {
      setAnalysisStatus('Monitoring stopped');
      setIsRecording(false);
      setLastAnalysisResult(null);
    }
  }, [isMonitoring, cameraStatus.active]);

  // Remove simulated data generation - Detection Confidence will only update with real incidents

  const startCamera = async () => {
    try {
      const response = await fetch('http://localhost:8000/camera/start', { 
        method: 'POST' 
      });
      const result = await response.json();
      setCameraStatus(prev => ({ ...prev, active: result.active }));
      setCameraError(null);
      return true;
    } catch (error) {
      console.error('Error starting camera:', error);
      setCameraError('Failed to start camera');
      return false;
    }
  };

  const stopCamera = async () => {
    try {
      const response = await fetch('http://localhost:8000/camera/stop', { 
        method: 'POST' 
      });
      const result = await response.json();
      setCameraStatus(prev => ({ ...prev, active: result.active }));
    } catch (error) {
      console.error('Error stopping camera:', error);
      setCameraError('Failed to stop camera');
    }
  };

  // Check camera status on component mount
  useEffect(() => {
    const checkCameraStatus = async () => {
      try {
        const response = await fetch('http://localhost:8000/camera/status');
        const status = await response.json();
        setCameraStatus(status);
        
        if (!status.has_camera) {
          setCameraError('No camera detected');
        } else {
          setCameraError(null);
        }
      } catch (error) {
        console.error('Error checking camera status:', error);
        setCameraError('Failed to connect to camera server');
      }
    };

    checkCameraStatus();
    
    // Check camera status periodically
    const statusInterval = setInterval(checkCameraStatus, 10000);
    return () => clearInterval(statusInterval);
  }, []);

  // Stop camera when monitoring stops (cleanup effect)
  useEffect(() => {
    if (!isMonitoring && cameraStatus.active) {
      stopCamera();
    }
  }, [isMonitoring, cameraStatus.active, stopCamera]);

  // Handle monitoring state changes
  const handleMonitoringToggle = async () => {
    if (isMonitoring) {
      // Stop monitoring and camera
      setIsMonitoring(false);
      await stopCamera();
    } else {
      // Start monitoring and camera
      if (cameraStatus.has_camera) {
        const success = await startCamera();
        if (success !== false) {
          setIsMonitoring(true);
        }
      } else {
        setCameraError('No camera available to start monitoring');
      }
    }
  };

  // Function to handle opening video files
  const handleVideoClick = (notification) => {
    const videoUrl = `http://localhost:8000/video/${encodeURIComponent(notification.filename)}`;
    window.open(videoUrl, '_blank');
  };

  const VideoFeed = ({ cameraId, title }) => (
    <div className="video-feed">
      <h3>{title}</h3>
      <div className="video-container">
        {cameraError ? (
          <div className="video-error">
            <div className="camera-icon">❌</div>
            <p>{cameraError}</p>
            <div className="error-help">
              <p>Use the "Start Monitoring" button to activate the camera</p>
            </div>
          </div>
        ) : cameraStatus.active && isMonitoring ? (
          <div className="live-video">
            <img 
              src="http://localhost:8000/video_stream" 
              alt="Live Camera Feed"
              className="video-stream"
              onError={() => setCameraError('Video stream error')}
            />
            <div className="status-indicator active"></div>
            <div className="live-badge">🔴 LIVE</div>
            
            {/* Recording indicator */}
            {isRecording && (
              <div className="recording-indicator">
                <div className="recording-dot"></div>
                <span>REC</span>
              </div>
            )}
            
            {/* Analysis status overlay */}
            <div className="analysis-overlay">
              <div className="analysis-status">
                <span className="status-text">{analysisStatus}</span>
                {clipCount > 0 && (
                  <span className="clip-counter">Clips: {clipCount}</span>
                )}
              </div>
              
              {/* Detection result indicator */}
              {lastAnalysisResult && (
                <div className={`detection-result ${lastAnalysisResult.violence_detected ? 'violence-detected' : 'safe'}`}>
                  {lastAnalysisResult.violence_detected ? (
                    <>
                      <div className="result-icon">🚨</div>
                      <div className="result-text">
                        <div className="result-status">INCIDENT DETECTED</div>
                        <div className="result-classification">{lastAnalysisResult.classification}</div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="result-icon">✅</div>
                      <div className="result-text">
                        <div className="result-status">SAFE</div>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="video-placeholder">
            <div className="camera-icon">📹</div>
            <p>Camera {cameraId}</p>
            <div className="status-message">
              {!cameraStatus.has_camera ? 
                'No camera detected' : 
                'Click "Start Monitoring" to begin live feed'
              }
            </div>
            <div className={`status-indicator ${cameraStatus.has_camera ? 'ready' : 'inactive'}`}></div>
          </div>
        )}
      </div>
    </div>
  );

  const DetectionGraph = () => (
    <div className="graph-container">
      <h3>Detection Confidence Over Time</h3>
      <div className="graph">
        {detectionData.map((data, index) => (
          <div 
            key={index} 
            className="bar" 
            style={{ 
              height: `${data.confidence}%`,
              backgroundColor: data.confidence > 80 ? '#ff4444' : 
                             data.confidence > 50 ? '#ffaa44' : '#44ff44'
            }}
            title={`${data.timestamp}: ${data.confidence.toFixed(1)}%`}
          ></div>
        ))}
      </div>
    </div>
  );

  const ViolentIncidentGraph = () => {
    const maxCount = Math.max(...violentIncidentData.map(d => d.count), 1);
    
    return (
      <div className="graph-container violent-incident-graph">
        <h3>🚨 Violent Incidents Over Time</h3>
        <div className="graph">
          {violentIncidentData.length === 0 ? (
            <div className="no-data">No violent incidents recorded</div>
          ) : (
            violentIncidentData.map((data, index) => (
              <div 
                key={index} 
                className="incident-bar" 
                style={{ 
                  height: `${(data.count / maxCount) * 100}%`,
                  backgroundColor: '#ff4444',
                  minHeight: data.count > 0 ? '10px' : '2px'
                }}
                title={`${data.timeLabel}: ${data.count} incident${data.count !== 1 ? 's' : ''}`}
              >
                <span className="bar-count">{data.count}</span>
              </div>
            ))
          )}
        </div>
        <div className="graph-axis">
          {violentIncidentData.map((data, index) => (
            <div key={index} className="axis-label">
              {data.timeLabel}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const AlertsPanel = () => (
    <div className="alerts-panel">
      <h3>Recent Detections</h3>
      <div className="alerts-list">
        {detectionData.slice(-5).reverse().map((alert, index) => (
          <div key={index} className={`alert-item ${alert.severity.toLowerCase()}`}>
            <div className="alert-info">
              <span className="alert-time">{alert.timestamp}</span>
              <span className="alert-location">{alert.location}</span>
            </div>
            <div className="alert-details">
              <span className="confidence">{alert.confidence.toFixed(1)}%</span>
              <span className={`severity ${alert.severity.toLowerCase()}`}>
                {alert.severity}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const ViolentVideoNotifications = () => (
    <div className="violent-notifications">
      <h3>🚨 Violent Incident Alerts</h3>
      <div className="connection-status">
        <span className={`status-dot ${wsConnection ? 'connected' : 'disconnected'}`}></span>
        WebSocket: {wsConnection ? 'Connected' : 'Disconnected'}
      </div>
      <div className="notifications-list">
        {violentVideoNotifications.length === 0 ? (
          <div className="no-notifications">No violent incidents detected yet</div>
        ) : (
          violentVideoNotifications.map((notification) => (
            <div 
              key={notification.id} 
              className="notification-item violent-alert clickable"
              onClick={() => handleVideoClick(notification)}
              title={`Click to open ${notification.filename}`}
            >
              <div className="notification-icon">🚨</div>
              <div className="notification-content">
                <div className="notification-message">{notification.message}</div>
                <div className="notification-time">{notification.timestamp}</div>
                <div className="click-hint">📹 Click to view video</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );

  const ReportNotifications = () => (
    <div className="report-notifications">
      <h3>📄 Analysis Reports</h3>
      <div className="notifications-list">
        {reportNotifications.length === 0 ? (
          <div className="no-notifications">No reports generated yet</div>
        ) : (
          reportNotifications.map((notification) => (
            <div key={notification.id} className={`notification-item ${notification.violenceDetected ? 'report-violent' : 'report-safe'}`}>
              <div className="notification-icon">{notification.violenceDetected ? '🚨' : '✅'}</div>
              <div className="notification-content">
                <div className="notification-message">{notification.message}</div>
                <div className="notification-details">
                  <span className="report-classification">{notification.classification}</span>
                  <span className="notification-time">{notification.timestamp}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );

  return (
    <div className="App">
      <header className="dashboard-header">
        <h1>🛡️ Bully Detection System</h1>
        <div className="header-controls">
          <div className="stats">
            <span className="stat">
              <strong>{alertCount}</strong> Alerts Today
            </span>
            <span className="stat">
              <strong>{cameraStatus.active ? '1' : '0'}</strong> Camera Active
            </span>
            <span className="stat camera-status">
              {cameraStatus.has_camera ? 
                (cameraStatus.active ? '🟢 Live' : '🟡 Ready') : 
                '🔴 No Camera'
              }
            </span>
          </div>
          <button 
            className={`monitor-btn ${isMonitoring ? 'active' : ''}`}
            onClick={handleMonitoringToggle}
            disabled={!cameraStatus.has_camera && !isMonitoring}
          >
            {isMonitoring ? '⏸️ Stop' : '▶️ Start'} Monitoring
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="video-grid">
          <VideoFeed cameraId={1} title="Main Hallway" />
        </div>

        <div className="analytics-section">
          <DetectionGraph />
          <ViolentIncidentGraph />
          {/* <AlertsPanel /> */}
          <ViolentVideoNotifications />
          <ReportNotifications />
        </div>
      </main>
    </div>
  );
}

export default App;
