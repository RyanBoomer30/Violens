import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [detectionData, setDetectionData] = useState([]);
  const [alertCount, setAlertCount] = useState(0);
  const [isMonitoring, setIsMonitoring] = useState(false);

  // Simulate real-time detection data
  useEffect(() => {
    const interval = setInterval(() => {
      if (isMonitoring) {
        const newData = {
          timestamp: new Date().toLocaleTimeString(),
          confidence: Math.random() * 100,
          location: `Camera ${Math.floor(Math.random() * 4) + 1}`,
          severity: Math.random() > 0.7 ? 'High' : Math.random() > 0.4 ? 'Medium' : 'Low'
        };
        
        setDetectionData(prev => [...prev.slice(-9), newData]);
        
        if (newData.confidence > 80) {
          setAlertCount(prev => prev + 1);
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isMonitoring]);

  const VideoFeed = ({ cameraId, title }) => (
    <div className="video-feed">
      <h3>{title}</h3>
      <div className="video-placeholder">
        <div className="camera-icon">📹</div>
        <p>Camera {cameraId}</p>
        <div className="status-indicator active"></div>
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
              <strong>4</strong> Cameras Active
            </span>
          </div>
          <button 
            className={`monitor-btn ${isMonitoring ? 'active' : ''}`}
            onClick={() => setIsMonitoring(!isMonitoring)}
          >
            {isMonitoring ? '⏸️ Pause' : '▶️ Start'} Monitoring
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="video-grid">
          <VideoFeed cameraId={1} title="Main Hallway" />
          <VideoFeed cameraId={2} title="Cafeteria" />
          <VideoFeed cameraId={3} title="Playground" />
          <VideoFeed cameraId={4} title="Classroom Wing" />
        </div>

        <div className="analytics-section">
          <DetectionGraph />
          <AlertsPanel />
        </div>
      </main>
    </div>
  );
}

export default App;
