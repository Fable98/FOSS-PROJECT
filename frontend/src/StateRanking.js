/**
 * StateRanking.js — SubTerra Phase 4
 * State & District comparison dashboard with ranking charts.
 * Shows all states ranked by Resource Availability Index.
 */
import React, { useState, useEffect } from 'react';
import './StateRanking.css';

const API_BASE = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
const API = `${API_BASE}/api`;

const STATUS = {
  safe:           { label: 'Safe',           color: '#00e5a0' },
  semi_critical:  { label: 'Semi-Critical',  color: '#f5c842' },
  critical:       { label: 'Critical',       color: '#ff6b4a' },
  over_exploited: { label: 'Over-Exploited', color: '#ff2d55' },
  no_data:        { label: 'No Data',        color: '#4a6fa5' },
};

// ── Horizontal bar chart ───────────────────────────────────────
function HBar({ label, value, max, color, sub, onClick, active }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={`hbar-row ${active ? 'active' : ''}`} onClick={onClick}
      style={{ '--hbar-color': color }}>
      <div className="hbar-label">{label}</div>
      <div className="hbar-track">
        <div className="hbar-fill" style={{ width: `${pct}%`, background: color }} />
        <div className="hbar-value">{value}</div>
      </div>
      <div className="hbar-sub" style={{ color }}>{sub}</div>
    </div>
  );
}

// ── Mini stat ──────────────────────────────────────────────────
function MiniStat({ label, value, color = '#00c8ff' }) {
  return (
    <div className="mini-stat">
      <div className="ms-val" style={{ color }}>{value}</div>
      <div className="ms-lbl">{label}</div>
    </div>
  );
}

export default function StateRanking({ onSelectStation }) {
  const [states, setStates]         = useState([]);
  const [districts, setDistricts]   = useState([]);
  const [selected, setSelected]     = useState(null);
  const [loading, setLoading]       = useState(true);
  const [loadingDistrict, setLoadingDistrict] = useState(false);
  const [view, setView]             = useState('states'); // 'states' | 'districts'
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetch(`${API}/ranking/states`)
      .then(r => r.json())
      .then(d => { setStates(d.states || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const selectState = async (state) => {
    setSelected(state);
    setView('districts');
    setLoadingDistrict(true);
    try {
      const r = await fetch(`${API}/ranking/districts/${encodeURIComponent(state.state)}`);
      const d = await r.json();
      setDistricts(d.districts || []);
    } catch { setDistricts([]); }
    setLoadingDistrict(false);
  };

  // Status counts
  const statusCounts = states.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] || 0) + 1;
    return acc;
  }, {});

  const filteredStates = states.filter(s =>
    s.state.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const worstStates   = states.slice(0, 5);
  const bestStates    = [...states].sort((a,b) => b.rai - a.rai).slice(0, 5);
  const avgRAI        = states.length ? Math.round(states.reduce((s, x) => s + x.rai, 0) / states.length) : 0;
  const criticalCount = states.filter(s => s.status === 'critical' || s.status === 'over_exploited').length;

  return (
    <div className="ranking-page">

      {/* ── Top KPIs ── */}
      <div className="ranking-kpis">
        <div className="rk-card">
          <div className="rk-val" style={{ color: '#00c8ff' }}>{states.length}</div>
          <div className="rk-lbl">States Monitored</div>
        </div>
        <div className="rk-card">
          <div className="rk-val" style={{ color: avgRAI > 60 ? '#00e5a0' : avgRAI > 40 ? '#f5c842' : '#ff6b4a' }}>
            {avgRAI}
          </div>
          <div className="rk-lbl">Avg RAI Score</div>
        </div>
        <div className="rk-card">
          <div className="rk-val" style={{ color: criticalCount > 0 ? '#ff2d55' : '#00e5a0' }}>
            {criticalCount}
          </div>
          <div className="rk-lbl">Critical / Over-Exploited States</div>
        </div>
        <div className="rk-card">
          <div className="rk-val" style={{ color: '#f5c842' }}>
            {statusCounts.safe || 0}
          </div>
          <div className="rk-lbl">Safe States</div>
        </div>

        {/* Export all button */}
        <a href={`${API}/export/summary/csv`} className="export-all-btn" download>
          ⬇ Export All Stations CSV
        </a>
      </div>

      {/* ── Status breakdown ── */}
      <div className="status-breakdown">
        {Object.entries(STATUS).filter(([k]) => k !== 'no_data').map(([key, val]) => (
          <div key={key} className="sb-item" style={{ '--sc': val.color }}>
            <div className="sb-bar" style={{
              height: `${Math.max(4, ((statusCounts[key] || 0) / Math.max(states.length, 1)) * 80)}px`,
              background: val.color,
            }} />
            <div className="sb-count" style={{ color: val.color }}>{statusCounts[key] || 0}</div>
            <div className="sb-label">{val.label}</div>
          </div>
        ))}
      </div>

      {/* ── Main content ── */}
      <div className="ranking-grid">

        {/* Left: full state list */}
        <div className="ranking-panel">
          <div className="rp-header">
            <div className="rp-title">
              {view === 'states' ? '🗺️ All States — Ranked by RAI' : `📍 Districts in ${selected?.state}`}
              {view === 'districts' && (
                <button className="back-to-states" onClick={() => setView('states')}>
                  ← All States
                </button>
              )}
            </div>
            {view === 'states' && (
              <input
                className="search-input"
                placeholder="Search state..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
              />
            )}
          </div>

          {loading ? (
            <div className="rp-loading">Loading state data...</div>
          ) : view === 'states' ? (
            <div className="hbar-list">
              {filteredStates.map((s, i) => {
                const st = STATUS[s.status] || STATUS.no_data;
                return (
                  <HBar
                    key={s.state}
                    label={`${i + 1}. ${s.state}`}
                    value={s.rai}
                    max={100}
                    color={st.color}
                    sub={`${st.label} · ${s.avg_water_level_m}m avg · ${s.total_stations} stations`}
                    onClick={() => selectState(s)}
                    active={selected?.state === s.state}
                  />
                );
              })}
            </div>
          ) : loadingDistrict ? (
            <div className="rp-loading">Loading district data...</div>
          ) : (
            <div className="hbar-list">
              {districts.map((d, i) => {
                const st = STATUS[d.status] || STATUS.no_data;
                return (
                  <HBar
                    key={d.district}
                    label={`${i + 1}. ${d.district}`}
                    value={d.rai}
                    max={100}
                    color={st.color}
                    sub={`${st.label} · ${d.avg_water_level_m}m avg · ${d.total_stations} stations`}
                    onClick={() => {}}
                    active={false}
                  />
                );
              })}
              {districts.length === 0 && (
                <div className="rp-empty">No district data available</div>
              )}
            </div>
          )}
        </div>

        {/* Right: insights */}
        <div className="insights-panel">

          {/* Most stressed */}
          <div className="insight-card">
            <div className="ic-title">🔴 Most Stressed States</div>
            {worstStates.map((s, i) => {
              const st = STATUS[s.status] || STATUS.no_data;
              return (
                <div key={s.state} className="ic-row" onClick={() => selectState(s)}
                  style={{ cursor: 'pointer' }}>
                  <span className="ic-rank" style={{ color: st.color }}>{i + 1}</span>
                  <div className="ic-info">
                    <div className="ic-name">{s.state}</div>
                    <div className="ic-detail">{s.avg_water_level_m}m avg · {s.total_stations} stations</div>
                  </div>
                  <div className="ic-rai" style={{ color: st.color }}>{s.rai}</div>
                </div>
              );
            })}
          </div>

          {/* Best performing */}
          <div className="insight-card">
            <div className="ic-title">🟢 Best Performing States</div>
            {bestStates.map((s, i) => {
              const st = STATUS[s.status] || STATUS.no_data;
              return (
                <div key={s.state} className="ic-row" onClick={() => selectState(s)}
                  style={{ cursor: 'pointer' }}>
                  <span className="ic-rank" style={{ color: st.color }}>{i + 1}</span>
                  <div className="ic-info">
                    <div className="ic-name">{s.state}</div>
                    <div className="ic-detail">{s.avg_water_level_m}m avg · {s.total_stations} stations</div>
                  </div>
                  <div className="ic-rai" style={{ color: st.color }}>{s.rai}</div>
                </div>
              );
            })}
          </div>

          {/* CGWB reference */}
          <div className="insight-card">
            <div className="ic-title">📋 CGWB Classification</div>
            {Object.entries(STATUS).filter(([k]) => k !== 'no_data').map(([key, val]) => (
              <div key={key} className="cgwb-row">
                <div className="cgwb-dot" style={{ background: val.color }} />
                <div className="cgwb-label" style={{ color: val.color }}>{val.label}</div>
                <div className="cgwb-range">
                  {key === 'safe'           && '< 8m depth'}
                  {key === 'semi_critical'  && '8–15m depth'}
                  {key === 'critical'       && '15–25m depth'}
                  {key === 'over_exploited' && '> 25m depth'}
                </div>
              </div>
            ))}
          </div>

          {/* Selected state detail */}
          {selected && view === 'districts' && (
            <div className="insight-card selected-state">
              <div className="ic-title">📊 {selected.state}</div>
              <div className="selected-stats">
                <MiniStat label="Avg Level"    value={`${selected.avg_water_level_m}m`} color={STATUS[selected.status]?.color} />
                <MiniStat label="RAI Score"    value={selected.rai} color={STATUS[selected.status]?.color} />
                <MiniStat label="Status"       value={STATUS[selected.status]?.label} color={STATUS[selected.status]?.color} />
                <MiniStat label="Stations"     value={selected.total_stations} color="#00c8ff" />
              </div>
              <a href={`${API}/export/summary/csv`}
                className="export-btn-small" download>
                ⬇ Export {selected.state} Data
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
