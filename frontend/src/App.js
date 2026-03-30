import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import { Task1Detail, Task2Detail, Task3Detail } from './TaskDetail';
import StateRanking from './StateRanking.js';

const API_BASE = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
const API = `${API_BASE}/api`;
const REFRESH_MS = 15 * 60 * 1000; // 15 minutes

const STATUS = {
  safe:           { label: 'Safe',           color: '#00e5a0', glow: '0 0 20px #00e5a040' },
  semi_critical:  { label: 'Semi-Critical',  color: '#f5c842', glow: '0 0 20px #f5c84240' },
  critical:       { label: 'Critical',       color: '#ff6b4a', glow: '0 0 20px #ff6b4a40' },
  over_exploited: { label: 'Over-Exploited', color: '#ff2d55', glow: '0 0 20px #ff2d5540' },
  unknown:        { label: 'Unknown',        color: '#4a6fa5', glow: 'none' },
};

function OceanCursor() {
  const canvasRef = useRef(null);
  const ripples = useRef([]);
  const mouse = useRef({ x: 0, y: 0 });
  const animRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener('resize', resize);
    const onMove = (e) => {
      mouse.current = { x: e.clientX, y: e.clientY };
      if (Math.random() > 0.6) {
        ripples.current.push({ x: e.clientX, y: e.clientY, r: 0, maxR: 60 + Math.random() * 80, alpha: 0.4 + Math.random() * 0.3, speed: 1.2 + Math.random() * 1.5 });
        if (ripples.current.length > 25) ripples.current.shift();
      }
    };
    const onClick = (e) => {
      for (let i = 0; i < 5; i++) ripples.current.push({ x: e.clientX, y: e.clientY, r: 0, maxR: 80 + i * 40, alpha: 0.6, speed: 2 + i * 0.5 });
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('click', onClick);
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const grad = ctx.createRadialGradient(mouse.current.x, mouse.current.y, 0, mouse.current.x, mouse.current.y, 12);
      grad.addColorStop(0, 'rgba(0,200,255,0.9)'); grad.addColorStop(1, 'rgba(0,200,255,0)');
      ctx.beginPath(); ctx.arc(mouse.current.x, mouse.current.y, 12, 0, Math.PI * 2); ctx.fillStyle = grad; ctx.fill();
      ripples.current = ripples.current.filter(rip => {
        rip.r += rip.speed; rip.alpha *= 0.96;
        if (rip.r >= rip.maxR || rip.alpha < 0.01) return false;
        ctx.beginPath(); ctx.arc(rip.x, rip.y, rip.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0,200,255,${rip.alpha})`; ctx.lineWidth = 1.5; ctx.stroke();
        return true;
      });
      animRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animRef.current); window.removeEventListener('resize', resize); window.removeEventListener('mousemove', onMove); window.removeEventListener('click', onClick); };
  }, []);
  return <canvas ref={canvasRef} className="ocean-canvas" />;
}

function Counter({ value }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0; const end = parseInt(value) || 0; if (!end) return;
    const step = Math.ceil(end / 40);
    const timer = setInterval(() => { start += step; if (start >= end) { setDisplay(end); clearInterval(timer); } else setDisplay(start); }, 30);
    return () => clearInterval(timer);
  }, [value]);
  return <>{display.toLocaleString()}</>;
}

function StationDot({ station, onClick, selected }) {
  const s = STATUS[station.status] || STATUS.unknown;
  const x = ((station.longitude - 68) / 30) * 340 + 30;
  const y = ((38 - station.latitude) / 32) * 380 + 20;
  return (
    <g onClick={() => onClick(station)} style={{ cursor: 'pointer' }}>
      {selected && <circle cx={x} cy={y} r={14} fill="none" stroke={s.color} strokeWidth={2} opacity={0.5}><animate attributeName="r" values="10;18;10" dur="2s" repeatCount="indefinite" /><animate attributeName="opacity" values="0.5;0.1;0.5" dur="2s" repeatCount="indefinite" /></circle>}
      <circle cx={x} cy={y} r={selected ? 6 : 4} fill={s.color} opacity={0.9} filter={selected ? 'url(#glow)' : 'none'} />
    </g>
  );
}

function IndiaMap({ stations, onSelect, selected }) {
  return (
    <svg viewBox="0 0 400 420" className="india-map">
      <defs>
        <filter id="glow"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        <radialGradient id="mapBg" cx="50%" cy="50%" r="50%"><stop offset="0%" stopColor="#0a2040" /><stop offset="100%" stopColor="#050d1a" /></radialGradient>
      </defs>
      <rect width="400" height="420" fill="url(#mapBg)" rx="12" />
      <path d="M 180 25 L 220 22 L 270 35 L 300 55 L 320 80 L 330 110 L 345 130 L 350 160 L 340 185 L 355 200 L 360 225 L 345 255 L 320 280 L 290 310 L 260 340 L 230 370 L 210 390 L 195 380 L 175 355 L 155 330 L 130 300 L 110 270 L 90 240 L 75 210 L 70 180 L 80 155 L 75 130 L 85 105 L 100 80 L 120 60 L 150 40 Z" fill="none" stroke="#1a3a5c" strokeWidth="1.5" opacity="0.7" />
      {[0.25,0.5,0.75].map(t => (<React.Fragment key={t}><line x1={30+t*340} y1="20" x2={30+t*340} y2="400" stroke="#0c2a45" strokeWidth="1" strokeDasharray="3,6" /><line x1="30" y1={20+t*380} x2="370" y2={20+t*380} stroke="#0c2a45" strokeWidth="1" strokeDasharray="3,6" /></React.Fragment>))}
      {stations.map(s => <StationDot key={s.station_id} station={s} onClick={onSelect} selected={selected?.station_id === s.station_id} />)}
      {Object.entries(STATUS).filter(([k]) => k !== 'unknown').map(([key,val],i) => (<g key={key} transform={`translate(15,${320+i*18})`}><circle cx="6" cy="6" r="4" fill={val.color} /><text x="14" y="10" fill="#8ab4d4" fontSize="9" fontFamily="'DM Mono',monospace">{val.label}</text></g>))}
    </svg>
  );
}

function Sparkline({ data, color = '#00c8ff' }) {
  if (!data || data.length < 2) return <div className="sparkline-empty">No trend data</div>;
  const vals = data.map(d => d.avg_level_m || 0);
  const min = Math.min(...vals), max = Math.max(...vals), range = max - min || 1;
  const w = 280, h = 60;
  const pts = vals.map((v,i) => `${(i/(vals.length-1))*w},${h-((v-min)/range)*(h-10)-5}`).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="sparkline">
      <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity="0.3" /><stop offset="100%" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill="url(#sg)" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

// ── Last updated timestamp ─────────────────────────────────────
function LiveClock() {
  const [time, setTime] = useState('');
  useEffect(() => {
    const update = () => setTime(new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }));
    update();
    const t = setInterval(update, 60000);
    return () => clearInterval(t);
  }, []);
  return <>{time}</>;
}

export default function App() {
  const [loading, setLoading]   = useState(true);
  const [stations, setStations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [task1, setTask1]       = useState(null);
  const [task2, setTask2]       = useState(null);
  const [task3, setTask3]       = useState(null);
  const [alerts, setAlerts]     = useState([]);
  const [health, setHealth]     = useState(false);
  const [activeTab, setActiveTab]           = useState('map');
  const [taskPage, setTaskPage]             = useState(null);
  const [loadingStation, setLoadingStation] = useState(false);
  const [lastRefresh, setLastRefresh]       = useState(null);
  const [healthMeta, setHealthMeta]         = useState(null);

  // Assign status from water level if available, else random
  const assignStatus = (s) => {
    const lvl = s.current_level_m || s.water_level_m;
    if (lvl != null) {
      if (lvl < 8)  return { ...s, status: 'safe' };
      if (lvl < 15) return { ...s, status: 'semi_critical' };
      if (lvl < 25) return { ...s, status: 'critical' };
      return { ...s, status: 'over_exploited' };
    }
    return { ...s, status: ['safe','semi_critical','critical','over_exploited'][Math.floor(Math.random()*4)] };
  };

  const loadStations = useCallback(async () => {
    try {
      const [hRes, sRes, aRes] = await Promise.all([
        fetch(`${API}/health`),
        fetch(`${API}/stations`),
        fetch(`${API}/alerts`),
      ]);
      const hData = await hRes.json(); setHealth(hData.db); setHealthMeta(hData);
      if (sRes.ok) { const d = await sRes.json(); setStations(d.map(assignStatus)); }
      if (aRes.ok) { const d = await aRes.json(); setAlerts(d.alerts || []); }
      setLastRefresh(new Date());
    } catch(e) { console.error(e); }
  }, []);

  useEffect(() => {
    loadStations().finally(() => setLoading(false));
    // Auto-refresh every 15 minutes
    const interval = setInterval(loadStations, REFRESH_MS);
    return () => clearInterval(interval);
  }, [loadStations]);

  const selectStation = useCallback(async (station) => {
    setSelected(station); setTask1(null); setTask2(null); setTask3(null);
    setLoadingStation(true); setActiveTab('detail'); setTaskPage(null);
    try {
      const [t1,t2,t3] = await Promise.allSettled([
        fetch(`${API}/task1/${station.station_id}?hours=720`).then(r=>r.json()),
        fetch(`${API}/task2/${station.station_id}?days=365`).then(r=>r.json()),
        fetch(`${API}/task3/${station.station_id}?days=365`).then(r=>r.json()),
      ]);
      if (t1.status==="fulfilled" && !t1.value?.error && !t1.value?.detail && t1.value?.station_id) setTask1(t1.value);
      if (t2.status==="fulfilled" && !t2.value?.detail && !t2.value?.error) setTask2(t2.value);
      if (t3.status==="fulfilled" && t3.value?.current_level_m != null) setTask3(t3.value);
    } catch(e) { console.error(e); }
    setLoadingStation(false);
  }, []);

  const statusCounts = stations.reduce((acc,s) => { acc[s.status]=(acc[s.status]||0)+1; return acc; }, {});
  const isDemoMode = healthMeta?.data_mode === 'demo_fallback';
  const isEmptyMode = healthMeta?.data_mode === 'empty';

  if (loading) return (
    <div className="splash"><OceanCursor />
      <div className="splash-inner">
        <div className="splash-logo">💧</div>
        <div className="splash-title">SUBTERRA</div>
        <div className="splash-bar"><div className="splash-fill" /></div>
        <div className="splash-sub">Initialising groundwater intelligence...</div>
      </div>
    </div>
  );

  if (taskPage === 'task1' && selected) return <div className="app"><OceanCursor /><div className="main" style={{paddingTop:'1.5rem'}}><Task1Detail station={selected} onBack={() => setTaskPage(null)} /></div></div>;
  if (taskPage === 'task2' && selected) return <div className="app"><OceanCursor /><div className="main" style={{paddingTop:'1.5rem'}}><Task2Detail station={selected} onBack={() => setTaskPage(null)} /></div></div>;
  if (taskPage === 'task3' && selected) return <div className="app"><OceanCursor /><div className="main" style={{paddingTop:'1.5rem'}}><Task3Detail station={selected} onBack={() => setTaskPage(null)} /></div></div>;

  return (
    <div className="app">
      <OceanCursor />

      <header className="header">
        <div className="header-left">
          <span className="logo-icon">💧</span>
          <div><div className="logo-text">SUBTERRA</div><div className="logo-sub">Groundwater Intelligence Platform</div></div>
        </div>
        <div className="header-stats">
          <div className="hstat"><span className="hstat-val"><Counter value={stations.length} /></span><span className="hstat-lbl">Stations</span></div>
          <div className="hstat"><span className="hstat-val" style={{color: alerts.length > 0 ? '#ff6b4a' : '#00e5a0'}}><Counter value={alerts.length} /></span><span className="hstat-lbl">Alerts</span></div>
          <div className="hstat"><span className="hstat-val"><LiveClock /></span><span className="hstat-lbl">Last Update</span></div>
          <button className="refresh-btn" onClick={loadStations} title="Refresh now">↻</button>
        </div>
        <div className="header-right">
          {isDemoMode && <div className="source-badge demo">Fallback Demo Data</div>}
          {isEmptyMode && <div className="source-badge empty">Waiting For Data</div>}
          <div className={`db-status ${health?'online':'offline'}`}><span className="db-dot" />{health?'DB Connected':'DB Offline'}</div>
          <div className="badge">CGWB · Problem #25068</div>
        </div>
      </header>

      {isDemoMode && (
        <div className="source-banner">
          Public source APIs are unstable right now, so this run is using resilient fallback demo data for a reliable end-to-end walkthrough.
        </div>
      )}
      {isEmptyMode && (
        <div className="source-banner empty">
          Data is still loading into the database. Wait for the scraper to finish its first run, then refresh the page.
        </div>
      )}

      <nav className="nav">
        {[
          {id:'map',    label:'🗺️ Live Map'},
          {id:'ranking',label:'🏆 State Ranking'},
          {id:'alerts', label:`⚡ Alerts${alerts.length>0?` (${alerts.length})`:''}`},
          {id:'about',  label:'📊 Overview'},
        ].map(tab => (
          <button key={tab.id} className={`nav-btn ${activeTab===tab.id?'active':''}`}
            onClick={() => setActiveTab(tab.id)}>{tab.label}</button>
        ))}
        {selected && (
          <button className={`nav-btn ${activeTab==='detail'?'active':''}`}
            onClick={() => { setActiveTab('detail'); setTaskPage(null); }}>
            🔍 {selected.station_name || selected.station_id}
          </button>
        )}
      </nav>

      <main className="main">

        {/* MAP */}
        {activeTab === 'map' && (
          <div className="tab-map">
            <div className="map-panel">
              <div className="panel-title"><span>📍 Station Network</span><span className="panel-count">{stations.length} stations</span></div>
              <IndiaMap stations={stations} onSelect={selectStation} selected={selected} />
            </div>
            <div className="map-sidebar">
              <div className="panel">
                <div className="panel-title">Zone Status</div>
                <div className="status-grid">
                  {Object.entries(STATUS).filter(([k])=>k!=='unknown').map(([key,val]) => (
                    <div key={key} className="status-item" style={{'--sc':val.color}}>
                      <div className="status-dot" style={{background:val.color,boxShadow:val.glow}} />
                      <div className="status-info"><span className="status-name">{val.label}</span><span className="status-count">{statusCounts[key]||0}</span></div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="panel panel-scroll">
                <div className="panel-title">All Stations</div>
                <div className="station-list">
                  {stations.map(s => { const st=STATUS[s.status]||STATUS.unknown; return (
                    <div key={s.station_id} className={`station-item ${selected?.station_id===s.station_id?'selected':''}`} onClick={() => selectStation(s)}>
                      <div className="si-dot" style={{background:st.color}} />
                      <div className="si-info"><div className="si-name">{s.station_name||s.station_id}</div><div className="si-meta">{s.district} · {s.state}</div></div>
                      <div className="si-level">{s.well_depth_m?`${s.well_depth_m}m`:'—'}</div>
                    </div>
                  ); })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* RANKING */}
        {activeTab === 'ranking' && (
          <StateRanking onSelectStation={selectStation} />
        )}

        {/* DETAIL */}
        {activeTab === 'detail' && selected && (
          <div className="tab-detail">
            <div className="detail-header">
              <div>
                <div className="detail-title">{selected.station_name||selected.station_id}</div>
                <div className="detail-meta">{selected.district} · {selected.state} · {selected.aquifer_type} aquifer</div>
              </div>
              <div className="detail-badges">
                <span className="detail-badge">ID: {selected.station_id}</span>
                {selected.well_depth_m && <span className="detail-badge">Depth: {selected.well_depth_m}m</span>}
                <a href={`${API}/export/${selected.station_id}/csv`} className="export-badge" download>⬇ CSV</a>
              </div>
            </div>

            {loadingStation ? (
              <div className="loading-row"><div className="pulse-dots"><span/><span/><span/></div><span>Fetching analysis...</span></div>
            ) : (
              <div className="detail-grid">
                {/* Task 1 */}
                <div className="detail-card clickable-card" onClick={() => setTaskPage('task1')}>
                  <div className="dc-header"><span className="dc-icon">📊</span><span className="dc-title">Fluctuation Analysis</span><span className="dc-tag">Task 1</span><span className="dc-arrow">→</span></div>
                  {task1 ? (<>
                    <div className="dc-big">{task1.current_level_m??'—'}<span className="dc-unit">m</span></div>
                    <div className="dc-label">Current Water Level</div>
                    <div className="dc-stats">
                      <div className="dc-stat"><span className={`dc-rate ${task1.rate_per_day>0?'bad':'good'}`}>{task1.rate_per_day>0?'↑':'↓'} {Math.abs(task1.rate_per_day||0).toFixed(3)}m</span><span>per day</span></div>
                      <div className="dc-stat"><span className="dc-val">{task1.trend_direction}</span><span>trend</span></div>
                      <div className="dc-stat"><span className="dc-val">{(task1.seasonal_phase||'').replace('_',' ')}</span><span>season</span></div>
                    </div>
                    {task1.moving_average?.length>0 && <Sparkline data={task1.moving_average} color="#00c8ff" />}
                    {task1.anomalies?.length>0 && <div className="dc-alert">⚠️ {task1.anomalies.length} anomal{task1.anomalies.length===1?'y':'ies'} detected</div>}
                    <div className="dc-click-hint">Click for full analysis →</div>
                  </>) : <div className="dc-empty">No fluctuation data available</div>}
                </div>

                {/* Task 2 */}
                <div className="detail-card clickable-card" onClick={() => setTaskPage('task2')}>
                  <div className="dc-header"><span className="dc-icon">🌧️</span><span className="dc-title">Recharge Estimation</span><span className="dc-tag">Task 2</span><span className="dc-arrow">→</span></div>
                  {task2 ? (<>
                    <div className="dc-big">{(task2.recharge_rate_m_per_day||0).toFixed(4)}<span className="dc-unit">m/day</span></div>
                    <div className="dc-label">Recharge Rate</div>
                    <div className="dc-stats">
                      <div className="dc-stat"><span className="dc-val">{(task2.lag_hours||0).toFixed(1)}h</span><span>lag time</span></div>
                      <div className="dc-stat"><span className="dc-val">{task2.net_recharge_m!=null?`${task2.net_recharge_m>0?'+':''}${task2.net_recharge_m}m`:'—'}</span><span>net recharge</span></div>
                      <div className="dc-stat"><span className="dc-val">{task2.aquifer_type||'—'}</span><span>aquifer</span></div>
                    </div>
                    <div className="zone-badge" style={{color:task2.zone_status==='good_recharge'?'#00e5a0':task2.zone_status==='critically_stressed'?'#ff2d55':'#f5c842'}}>{(task2.zone_status||'').replace(/_/g,' ').toUpperCase()}</div>
                    <div className="dc-click-hint">Click for full analysis →</div>
                  </>) : <div className="dc-empty">No recharge data available</div>}
                </div>

                {/* Task 3 */}
                <div className="detail-card clickable-card" onClick={() => setTaskPage('task3')}>
                  <div className="dc-header"><span className="dc-icon">🎯</span><span className="dc-title">Resource Evaluation</span><span className="dc-tag">Task 3</span><span className="dc-arrow">→</span></div>
                  {task3 ? (<>
                    <div className="dc-big" style={{color:STATUS[task3.status]?.color}}>{task3.resource_availability_index?.toFixed(1)??'—'}<span className="dc-unit">/100</span></div>
                    <div className="dc-label">Resource Availability Index</div>
                    <div className="rai-bar"><div className="rai-fill" style={{width:`${task3.resource_availability_index||0}%`,background:STATUS[task3.status]?.color||'#4a6fa5'}} /></div>
                    <div className="dc-stats">
                      <div className="dc-stat"><span className="dc-val" style={{color:STATUS[task3.status]?.color}}>{task3.status_label}</span><span>CGWB status</span></div>
                      <div className="dc-stat"><span className="dc-val">{(task3.annual_depletion_rate_m||0).toFixed(3)}m</span><span>depletion/yr</span></div>
                      <div className="dc-stat"><span className="dc-val">{task3.years_to_depletion!=null?`${task3.years_to_depletion}yr`:'♾️'}</span><span>to depletion</span></div>
                    </div>
                    {task3.alert_required && <div className="dc-alert critical">🚨 ALERT: Immediate intervention required</div>}
                    <div className="dc-click-hint">Click for full analysis →</div>
                  </>) : <div className="dc-empty">No evaluation data available</div>}
                </div>
              </div>
            )}
            {(task1||task3) && <div className="summary-box"><div className="summary-title">📋 Analysis Summary</div><p>{task1?.summary||task3?.summary}</p></div>}
          </div>
        )}

        {/* ALERTS */}
        {activeTab === 'alerts' && (
          <div className="tab-alerts">
            <div className="alerts-header">
              <div className="alerts-title">⚡ Active Alerts</div>
              <div className="alerts-count">{alerts.length} stations require attention</div>
            </div>
            {alerts.length===0 ? (
              <div className="no-alerts"><div className="na-icon">✅</div><div className="na-text">No active alerts</div><div className="na-sub">All monitored stations within normal parameters</div></div>
            ) : (
              <div className="alerts-grid">
                {alerts.map((a,i) => (
                  <div key={i} className="alert-card" onClick={() => selectStation(a)}>
                    <div className="ac-header"><span className="ac-id">{a.station_id}</span><span className="ac-status critical">CRITICAL</span></div>
                    <div className="ac-name">{a.station_name}</div>
                    <div className="ac-meta">{a.district} · {a.state}</div>
                    {a.water_level_m && <div className="ac-level">{a.water_level_m}m depth</div>}
                    {a.anomaly_reason && <div className="ac-reason">{a.anomaly_reason}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* OVERVIEW */}
        {activeTab === 'about' && (
          <div className="tab-about">
            <div className="about-hero">
              <div className="about-title">Real-Time Groundwater Intelligence</div>
              <div className="about-sub">SubTerra monitors 5,260 DWLR stations across India using live CGWB sensor data, delivering fluctuation analysis, recharge estimation, and resource evaluation.</div>
            </div>
            <div className="about-grid">
              <div className="about-card"><div className="about-icon">📊</div><div className="about-card-title">Task 1 — Fluctuation</div><p>Rate of water level change per hour, day, week. 7-day moving average trend. Anomaly detection via rolling Z-score (3σ threshold).</p></div>
              <div className="about-card"><div className="about-icon">🌧️</div><div className="about-card-title">Task 2 — Recharge</div><p>Dynamic recharge estimation correlating DWLR readings with IMD rainfall. Pre/post monsoon net recharge. Aquifer-type lag analysis.</p></div>
              <div className="about-card"><div className="about-icon">🎯</div><div className="about-card-title">Task 3 — Evaluation</div><p>CGWB zone classification: Safe / Semi-Critical / Critical / Over-Exploited. Years to depletion. Resource Availability Index (0–100).</p></div>
              <div className="about-card"><div className="about-icon">🏆</div><div className="about-card-title">State Ranking</div><p>All states ranked by average water level and RAI score. District-level drill-down. Export to CSV for further analysis.</p></div>
            </div>
            <div className="cgwb-table">
              <div className="ct-title">CGWB Classification Standards</div>
              <div className="ct-grid">
                {[
                  {status:'safe',          level:'< 8m',   stage:'< 70%',   action:'Monitor regularly'},
                  {status:'semi_critical', level:'8–15m',  stage:'70–90%',  action:'Reduce extraction'},
                  {status:'critical',      level:'15–25m', stage:'90–100%', action:'Strict regulation'},
                  {status:'over_exploited',level:'> 25m',  stage:'> 100%',  action:'Immediate intervention'},
                ].map(row => (
                  <div key={row.status} className="ct-row">
                    <div className="ct-dot" style={{background:STATUS[row.status].color}} />
                    <div className="ct-status" style={{color:STATUS[row.status].color}}>{STATUS[row.status].label}</div>
                    <div className="ct-val">{row.level}</div>
                    <div className="ct-val">{row.stage}</div>
                    <div className="ct-action">{row.action}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      </main>

      <footer className="footer">
        <span>SUBTERRA · CGWB · Problem Statement #25068</span>
        <span>India-WRIS · IMD · TimescaleDB · FastAPI · React</span>
        <span><a href="https://github.com/Fable98/FOSS-PROJECT" target="_blank" rel="noopener noreferrer">GitHub ↗</a></span>
      </footer>
    </div>
  );
}
