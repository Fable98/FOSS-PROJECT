import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulate loading
    setTimeout(() => {
      setLoading(false);
    }, 1000);
  }, []);

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading SUBTERRA Dashboard...</p>
      </div>
    );
  }

  return (
    <div className="App">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <h1>🌊 SUBTERRA</h1>
          <p className="subtitle">Groundwater Intelligence Platform</p>
        </div>
        
        <div className="stats-container">
          <div className="stat-card">
            <span className="stat-value">5,260</span>
            <span className="stat-label">DWLR Stations</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">28</span>
            <span className="stat-label">States Covered</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">24/7</span>
            <span className="stat-label">Live Monitoring</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="main-content">
        <div className="welcome-section">
          <h2>Welcome to SUBTERRA Dashboard</h2>
          <p>Real-time groundwater monitoring across India</p>
        </div>

        <div className="features-grid">
          <div className="feature-box">
            <div className="feature-icon">🗺️</div>
            <h3>Interactive Map</h3>
            <p>Visualize 5,260+ DWLR stations on an interactive map</p>
            <div className="status-badge coming-soon">Coming in Week 1</div>
          </div>

          <div className="feature-box">
            <div className="feature-icon">📊</div>
            <h3>Water Level Charts</h3>
            <p>View historical trends and real-time data</p>
            <div className="status-badge coming-soon">Coming in Week 1</div>
          </div>

          <div className="feature-box">
            <div className="feature-icon">⚡</div>
            <h3>Alert System</h3>
            <p>Early warnings for critical water levels</p>
            <div className="status-badge planned">Coming in Week 2</div>
          </div>

          <div className="feature-box">
            <div className="feature-icon">🎯</div>
            <h3>Zone Classification</h3>
            <p>Identify safe, critical, and over-exploited zones</p>
            <div className="status-badge planned">Coming in Week 2</div>
          </div>

          <div className="feature-box">
            <div className="feature-icon">📈</div>
            <h3>Trend Analysis</h3>
            <p>Year-over-year comparisons and patterns</p>
            <div className="status-badge planned">Coming in Week 3</div>
          </div>

          <div className="feature-box">
            <div className="feature-icon">💧</div>
            <h3>Recharge Estimation</h3>
            <p>Dynamic groundwater recharge calculations</p>
            <div className="status-badge planned">Coming in Week 3</div>
          </div>
        </div>

        <div className="info-section">
          <h3>🚀 Project Status</h3>
          <div className="progress-bar">
            <div className="progress-fill" style={{width: '20%'}}>Week 1 - Setup Complete</div>
          </div>
          <p className="progress-text">Landing page ✅ | Dashboard skeleton ✅ | Next: Map integration 🔄</p>
        </div>
      </div>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <p>SUBTERRA © 2025 | SIH 2025 | FOSS Hackathon</p>
          <p className="footer-links">
            <a href="/landing.html">Home</a> · 
            <a href="https://github.com/Fable98/FOSS-PROJECT" target="_blank" rel="noopener noreferrer">GitHub</a> · 
            <span>Data: CGWB</span>
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;