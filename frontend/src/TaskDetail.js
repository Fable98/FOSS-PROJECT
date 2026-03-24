import React, { useState, useEffect } from 'react';
import './TaskDetail.css';

const API = 'http://127.0.0.1:8000/api';

// ── Mini SVG pie chart ─────────────────────────────────────────
function PieChart({ slices, size = 120 }) {
  const r = size / 2 - 8;
  const cx = size / 2, cy = size / 2;
  let cumulative = 0;
  const total = slices.reduce((s, sl) => s + sl.value, 0);
  if (total === 0) return null;

  const paths = slices.map((sl, i) => {
    const startAngle = (cumulative / total) * 2 * Math.PI - Math.PI / 2;
    cumulative += sl.value;
    const endAngle = (cumulative / total) * 2 * Math.PI - Math.PI / 2;
    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const large = endAngle - startAngle > Math.PI ? 1 : 0;
    return (
      <path key={i}
        d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`}
        fill={sl.color} opacity={0.9} stroke="#030d1a" strokeWidth={1.5} />
    );
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r + 6} fill="#0a1f35" />
      {paths}
      <circle cx={cx} cy={cy} r={r * 0.45} fill="#030d1a" />
    </svg>
  );
}

// ── Line chart ─────────────────────────────────────────────────
function LineChart({ data, xKey, yKey, color = '#00c8ff', label = '', height = 180 }) {
  if (!data || data.length < 2) return <div className="chart-empty">Insufficient data</div>;

  const vals = data.map(d => parseFloat(d[yKey]) || 0);
  const labels = data.map(d => d[xKey]);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const W = 500, H = height, pad = { t: 20, b: 30, l: 45, r: 10 };
  const iW = W - pad.l - pad.r;
  const iH = H - pad.t - pad.b;

  const pts = vals.map((v, i) => {
    const x = pad.l + (i / (vals.length - 1)) * iW;
    const y = pad.t + (1 - (v - min) / range) * iH;
    return [x, y];
  });

  const polyline = pts.map(p => p.join(',')).join(' ');
  const area = `${pad.l},${pad.t + iH} ${polyline} ${pad.l + iW},${pad.t + iH}`;

  // Y axis ticks
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(t => ({
    y: pad.t + (1 - t) * iH,
    val: (min + t * range).toFixed(2),
  }));

  // X axis labels (show max 6)
  const step = Math.max(1, Math.floor(labels.length / 6));
  const xLabels = labels.filter((_, i) => i % step === 0 || i === labels.length - 1);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="line-chart">
      <defs>
        <linearGradient id={`lg-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
        <filter id="point-glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Grid */}
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={pad.l} y1={t.y} x2={pad.l + iW} y2={t.y}
            stroke="#0e2a42" strokeWidth={1} strokeDasharray="3,5" />
          <text x={pad.l - 6} y={t.y + 4} textAnchor="end"
            fill="#3a5a75" fontSize="9" fontFamily="'DM Mono', monospace">{t.val}</text>
        </g>
      ))}

      {/* Area */}
      <polygon points={area} fill={`url(#lg-${color.replace('#', '')})`} />

      {/* Line */}
      <polyline points={polyline} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />

      {/* Points */}
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={3} fill={color} filter="url(#point-glow)" />
      ))}

      {/* Last point highlighted */}
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]}
        r={5} fill={color} stroke="#030d1a" strokeWidth={2} />

      {/* X labels */}
      {xLabels.map((lbl, i) => {
        const idx = labels.indexOf(lbl);
        const x = pad.l + (idx / (labels.length - 1)) * iW;
        return (
          <text key={i} x={x} y={H - 8} textAnchor="middle"
            fill="#3a5a75" fontSize="8" fontFamily="'DM Mono', monospace">
            {String(lbl).slice(-5)}
          </text>
        );
      })}

      {/* Axes */}
      <line x1={pad.l} y1={pad.t} x2={pad.l} y2={pad.t + iH} stroke="#163550" strokeWidth={1} />
      <line x1={pad.l} y1={pad.t + iH} x2={pad.l + iW} y2={pad.t + iH} stroke="#163550" strokeWidth={1} />

      {/* Label */}
      {label && (
        <text x={pad.l + iW / 2} y={pad.t - 6} textAnchor="middle"
          fill="#6a8faa" fontSize="10" fontFamily="'DM Mono', monospace">{label}</text>
      )}
    </svg>
  );
}

// ── Bar chart ──────────────────────────────────────────────────
function BarChart({ data, xKey, yKey, color = '#00c8ff', height = 160 }) {
  if (!data || data.length === 0) return <div className="chart-empty">No data</div>;

  const vals = data.map(d => parseFloat(d[yKey]) || 0);
  const labels = data.map(d => d[xKey]);
  const max = Math.max(...vals, 0.1);
  const W = 500, H = height, pad = { t: 10, b: 28, l: 40, r: 10 };
  const iW = W - pad.l - pad.r;
  const iH = H - pad.t - pad.b;
  const bw = Math.max(4, iW / vals.length - 3);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="bar-chart">
      {vals.map((v, i) => {
        const x = pad.l + (i / vals.length) * iW + (iW / vals.length - bw) / 2;
        const bh = (v / max) * iH;
        const y = pad.t + iH - bh;
        const alpha = 0.4 + (v / max) * 0.6;
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={bh}
              fill={color} opacity={alpha} rx={2} />
            {vals.length <= 12 && (
              <text x={x + bw / 2} y={H - 10} textAnchor="middle"
                fill="#3a5a75" fontSize="8" fontFamily="'DM Mono', monospace">
                {String(labels[i]).slice(-3)}
              </text>
            )}
          </g>
        );
      })}
      <line x1={pad.l} y1={pad.t + iH} x2={pad.l + iW} y2={pad.t + iH} stroke="#163550" strokeWidth={1} />
    </svg>
  );
}

// ── Gauge chart ────────────────────────────────────────────────
function Gauge({ value, max = 100, color = '#00c8ff', label = '' }) {
  const pct = Math.min(1, Math.max(0, value / max));
  const angle = pct * Math.PI;
  const r = 70, cx = 100, cy = 90;
  const startX = cx - r, startY = cy;
  const endX = cx + r * Math.cos(Math.PI - angle);
  const endY = cy - r * Math.sin(angle);
  const large = angle > Math.PI / 2 ? 1 : 0;

  return (
    <svg viewBox="0 0 200 110" className="gauge-chart">
      {/* Background arc */}
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none" stroke="#0e2a42" strokeWidth={14} strokeLinecap="round" />
      {/* Value arc */}
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 ${large} 1 ${endX} ${endY}`}
        fill="none" stroke={color} strokeWidth={14} strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 6px ${color}60)` }} />
      {/* Value text */}
      <text x={cx} y={cy - 10} textAnchor="middle"
        fill={color} fontSize="22" fontWeight="700" fontFamily="'Syne', sans-serif">
        {typeof value === 'number' ? value.toFixed(1) : value}
      </text>
      <text x={cx} y={cy + 8} textAnchor="middle"
        fill="#6a8faa" fontSize="9" fontFamily="'DM Mono', monospace">
        {label}
      </text>
    </svg>
  );
}

// ── Stat card ──────────────────────────────────────────────────
function StatCard({ icon, label, value, unit, color = '#00c8ff', sub }) {
  return (
    <div className="stat-card" style={{ '--card-color': color }}>
      <div className="sc-icon">{icon}</div>
      <div className="sc-val" style={{ color }}>{value}<span className="sc-unit">{unit}</span></div>
      <div className="sc-label">{label}</div>
      {sub && <div className="sc-sub">{sub}</div>}
    </div>
  );
}

// ── STATUS CONFIG ──────────────────────────────────────────────
const STATUS = {
  safe:           { label: 'Safe',           color: '#00e5a0' },
  semi_critical:  { label: 'Semi-Critical',  color: '#f5c842' },
  critical:       { label: 'Critical',       color: '#ff6b4a' },
  over_exploited: { label: 'Over-Exploited', color: '#ff2d55' },
  unknown:        { label: 'Unknown',        color: '#4a6fa5' },
};

// ══════════════════════════════════════════════════════════════
// TASK 1 DETAIL PAGE
// ══════════════════════════════════════════════════════════════
export function Task1Detail({ station, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [window7d, setWindow7d] = useState(168);

  useEffect(() => {
    const fetch1 = async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/task1/${station.station_id}?hours=${window7d}`);
        const d = await r.json();
        setData(d.error ? null : d);
      } catch { setData(null); }
      setLoading(false);
    };
    fetch1();
  }, [station.station_id, window7d]);

  const trendColor = data?.trend_direction === 'falling' ? '#00e5a0'
    : data?.trend_direction === 'rising' ? '#ff6b4a' : '#f5c842';

  const anomalyTypes = data?.anomalies?.reduce((acc, a) => {
    acc[a.type] = (acc[a.type] || 0) + 1;
    return acc;
  }, {}) || {};

  return (
    <div className="task-detail-page">
      {/* Back + header */}
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>← Back to Station</button>
        <div className="tdp-title-row">
          <div className="tdp-tag task1-tag">Task 1</div>
          <div>
            <div className="tdp-title">Water Level Fluctuation Analysis</div>
            <div className="tdp-sub">{station.station_name} · {station.district} · {station.state}</div>
          </div>
        </div>
      </div>

      {/* Window selector */}
      <div className="window-selector">
        <span className="ws-label">Analysis window:</span>
        {[
          { label: '24h', val: 24 },
          { label: '3 days', val: 72 },
          { label: '7 days', val: 168 },
          { label: '30 days', val: 720 },
        ].map(w => (
          <button key={w.val} className={`ws-btn ${window7d === w.val ? 'active' : ''}`}
            onClick={() => setWindow7d(w.val)}>{w.label}</button>
        ))}
      </div>

      {loading ? (
        <div className="tdp-loading">
          <div className="tdp-spinner" /><span>Running fluctuation analysis...</span>
        </div>
      ) : !data ? (
        <div className="tdp-empty">No fluctuation data available for this station.</div>
      ) : (
        <>
          {/* KPI row */}
          <div className="kpi-row">
            <StatCard icon="💧" label="Current Level" value={data.current_level_m?.toFixed(2) ?? '—'} unit="m" color="#00c8ff" sub={`as of ${data.as_of?.slice(0,10)}`} />
            // Line 292 example
<StatCard icon="💧" label="Rate / Hour" value={`${data.rate_per_hour > 0 ? '+' : ''}${data.rate_per_hour?.toFixed(2) ?? '-'}`} unit="m" />

// Line 293 example
<StatCard icon="📅" label="Rate / Day" value={`${data.rate_per_day > 0 ? '+' : ''}${data.rate_per_day?.toFixed(2) ?? '-'}`} unit="m" />

// Line 294 example
<StatCard icon="🗓️" label="Rate / Week" value={`${data.rate_per_week > 0 ? '+' : ''}${data.rate_per_week?.toFixed(2) ?? '-'}`} unit="m" /><StatCard icon="🌊" label="Season" value={data.seasonal_phase?.replace('_', ' ') ?? '—'} unit="" color="#f5c842" />
            <StatCard icon="⚠️" label="Anomalies" value={data.anomalies?.length ?? 0} unit="" color={data.anomalies?.length > 0 ? '#ff6b4a' : '#00e5a0'} />
          </div>

          {/* Main charts row */}
          <div className="charts-row">
            {/* Moving average trend */}
            <div className="chart-card wide">
              <div className="cc-title">📈 30-Day Moving Average Trend</div>
              <div className="cc-sub">Daily average water level (metres depth from surface)</div>
              <LineChart
                data={data.moving_average || []}
                xKey="date" yKey="avg_level_m"
                color="#00c8ff" label="Water Level (m)" height={200} />
            </div>

            {/* Trend gauge */}
            <div className="chart-card">
              <div className="cc-title">🎯 Trend Status</div>
              <Gauge value={Math.abs(data.trend_magnitude || 0)} max={5}
                color={trendColor} label="7-day change (m)" />
              <div className="trend-pill" style={{ background: trendColor + '20', color: trendColor, borderColor: trendColor + '40' }}>
                {data.trend_direction === 'rising'  && '↑ Rising — water table deepening'}
                {data.trend_direction === 'falling' && '↓ Falling — water table recovering'}
                {data.trend_direction === 'stable'  && '→ Stable'}
                {!data.trend_direction && '— Unknown'}
              </div>
              <div className="status-pill-large" style={{
                background: data.status === 'recovering' ? '#00e5a020' : '#ff6b4a20',
                color: data.status === 'recovering' ? '#00e5a0' : '#ff6b4a',
                borderColor: data.status === 'recovering' ? '#00e5a040' : '#ff6b4a40',
              }}>
                {data.status?.replace('_', ' ').toUpperCase()}
              </div>
            </div>
          </div>

          {/* Rates bar chart + anomaly breakdown */}
          <div className="charts-row">
            <div className="chart-card">
              <div className="cc-title">📊 Rate of Change Comparison</div>
              <BarChart
                data={[
                  { period: '/hr',   rate: Math.abs(data.rate_per_hour || 0) },
                  { period: '/day',  rate: Math.abs(data.rate_per_day  || 0) },
                  { period: '/week', rate: Math.abs(data.rate_per_week || 0) },
                ]}
                xKey="period" yKey="rate" color={trendColor} height={140} />
            </div>

            {/* Anomaly pie */}
            <div className="chart-card">
              <div className="cc-title">🔍 Anomaly Breakdown</div>
              {data.anomalies?.length > 0 ? (
                <>
                  <PieChart slices={[
                    { label: 'Sudden Drop', value: anomalyTypes.sudden_drop || 0, color: '#ff2d55' },
                    { label: 'Statistical', value: anomalyTypes.statistical || 0,  color: '#f5c842' },
                  ]} size={130} />
                  <div className="pie-legend">
                    <div className="pl-item"><span style={{background:'#ff2d55'}} />Sudden drop ({anomalyTypes.sudden_drop || 0})</div>
                    <div className="pl-item"><span style={{background:'#f5c842'}} />Statistical ({anomalyTypes.statistical || 0})</div>
                  </div>
                </>
              ) : (
                <div className="no-anomaly">✅ No anomalies detected</div>
              )}
            </div>

            {/* Total readings */}
            <div className="chart-card">
              <div className="cc-title">📋 Summary</div>
              <div className="summary-stats">
                <div className="ss-item">
                  <span className="ss-val">{data.total_readings?.toLocaleString()}</span>
                  <span className="ss-lbl">Total readings</span>
                </div>
                <div className="ss-item">
                  <span className="ss-val">{data.trend_magnitude?.toFixed(3)}m</span>
                  <span className="ss-lbl">7-day change</span>
                </div>
                <div className="ss-item">
                  <span className="ss-val">{data.seasonal_phase?.replace('_',' ')}</span>
                  <span className="ss-lbl">Monsoon phase</span>
                </div>
              </div>
              <div className="summary-text">{data.summary}</div>
            </div>
          </div>

          {/* Anomaly table */}
          {data.anomalies?.length > 0 && (
            <div className="anomaly-table">
              <div className="at-title">⚠️ Anomaly Event Log</div>
              <div className="at-grid">
                <div className="at-head">Timestamp</div>
                <div className="at-head">Type</div>
                <div className="at-head">Magnitude</div>
                <div className="at-head">Reason</div>
                {data.anomalies.map((a, i) => (
                  <React.Fragment key={i}>
                    <div className="at-cell mono">{a.timestamp?.slice(0,16)}</div>
                    <div className="at-cell">
                      <span className={`at-type ${a.type}`}>{a.type?.replace('_',' ')}</span>
                    </div>
                    <div className="at-cell mono">{a.magnitude_m?.toFixed(3)}m</div>
                    <div className="at-cell text2">{a.reason}</div>
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TASK 2 DETAIL PAGE
// ══════════════════════════════════════════════════════════════
export function Task2Detail({ station, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch2 = async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/task2/${station.station_id}?days=365`);
        const d = await r.json();
        setData(d.error ? null : d);
      } catch { setData(null); }
      setLoading(false);
    };
    fetch2();
  }, [station.station_id]);

  const zoneColor = {
    good_recharge:       '#00e5a0',
    moderate_recharge:   '#f5c842',
    stressed:            '#ff6b4a',
    critically_stressed: '#ff2d55',
    insufficient_data:   '#4a6fa5',
  }[data?.zone_status] || '#4a6fa5';

  return (
    <div className="task-detail-page">
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>← Back to Station</button>
        <div className="tdp-title-row">
          <div className="tdp-tag task2-tag">Task 2</div>
          <div>
            <div className="tdp-title">Dynamic Recharge Estimation</div>
            <div className="tdp-sub">{station.station_name} · {station.district} · {station.state}</div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="tdp-loading"><div className="tdp-spinner" /><span>Computing recharge estimates...</span></div>
      ) : !data ? (
        <div className="tdp-empty">No recharge data available — rainfall correlation requires at least one monsoon season of data.</div>
      ) : (
        <>
          {/* KPI row */}
          <div className="kpi-row">
            <StatCard icon="💧" label="Recharge Rate" value={data.recharge_rate_m_per_day?.toFixed(4) ?? '0'} unit="m/day" color="#00c8ff" />
            <StatCard icon="⏱️" label="Lag Time" value={data.lag_hours?.toFixed(1) ?? '—'} unit="hrs" color="#f5c842" sub="Rain → response" />
            <StatCard icon="🌧️" label="Net Recharge" value={data.net_recharge_m != null ? (data.net_recharge_m > 0 ? '+' : '') + data.net_recharge_m : '—'} unit="m" color={data.net_recharge_m > 0 ? '#00e5a0' : '#ff6b4a'} sub="post − pre monsoon" />
            <StatCard icon="📍" label="Pre-Monsoon" value={data.pre_monsoon_level_m?.toFixed(2) ?? '—'} unit="m" color="#6a8faa" />
            <StatCard icon="📍" label="Post-Monsoon" value={data.post_monsoon_level_m?.toFixed(2) ?? '—'} unit="m" color="#00c8ff" />
            <StatCard icon="🪨" label="Aquifer" value={data.aquifer_type || '—'} unit="" color="#f5c842" />
          </div>

          <div className="charts-row">
            {/* Zone gauge */}
            <div className="chart-card">
              <div className="cc-title">🎯 Zone Classification</div>
              <Gauge value={data.recharge_rate_m_per_day * 1000 || 0} max={500}
                color={zoneColor} label="recharge rate (mm/day)" />
              <div className="zone-badge-large" style={{
                background: zoneColor + '20', color: zoneColor, borderColor: zoneColor + '50'
              }}>
                {data.zone_status?.replace(/_/g, ' ').toUpperCase()}
              </div>
              <div className="zone-desc">
                {data.zone_status === 'good_recharge'       && 'Aquifer is actively recharging. Extraction within sustainable limits.'}
                {data.zone_status === 'moderate_recharge'   && 'Some recovery observed but below expected seasonal norms.'}
                {data.zone_status === 'stressed'            && 'Minimal recharge detected. Monitor closely.'}
                {data.zone_status === 'critically_stressed' && 'Zero or negative net recharge. Immediate action needed.'}
                {data.zone_status === 'insufficient_data'   && 'Insufficient seasonal data for classification.'}
              </div>
            </div>

            {/* Pre vs post monsoon */}
            <div className="chart-card wide">
              <div className="cc-title">🌦️ Pre vs Post Monsoon Water Levels</div>
              <div className="cc-sub">Lower value = deeper water table</div>
              {data.pre_monsoon_level_m != null && data.post_monsoon_level_m != null ? (
                <>
                  <BarChart
                    data={[
                      { period: 'Pre-Monsoon',  level: data.pre_monsoon_level_m },
                      { period: 'Post-Monsoon', level: data.post_monsoon_level_m },
                    ]}
                    xKey="period" yKey="level"
                    color="#00c8ff" height={150} />
                  <div className="monsoon-compare">
                    <div className="mc-item">
                      <span className="mc-label">Pre-monsoon</span>
                      <span className="mc-val" style={{color:'#f5c842'}}>{data.pre_monsoon_level_m?.toFixed(3)}m</span>
                    </div>
                    <div className="mc-arrow" style={{color: data.net_recharge_m > 0 ? '#00e5a0' : '#ff6b4a'}}>
                      {data.net_recharge_m > 0 ? '↓ Improved' : '↑ Worsened'} by {Math.abs(data.net_recharge_m || 0).toFixed(3)}m
                    </div>
                    <div className="mc-item">
                      <span className="mc-label">Post-monsoon</span>
                      <span className="mc-val" style={{color:'#00c8ff'}}>{data.post_monsoon_level_m?.toFixed(3)}m</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="chart-empty">Monsoon season data not yet available</div>
              )}
            </div>
          </div>

          {/* Recharge events */}
          <div className="charts-row">
            <div className="chart-card wide">
              <div className="cc-title">⚡ Recharge Events (Last 10)</div>
              <div className="cc-sub">Individual rainfall → water level recovery events</div>
              {data.recharge_events?.length > 0 ? (
                <>
                  <LineChart
                    data={data.recharge_events.slice().reverse()}
                    xKey="date" yKey="recovery_m"
                    color="#00e5a0" label="Recovery (m)" height={160} />
                  <div className="events-table">
                    <div className="et-head">Date</div>
                    <div className="et-head">Rainfall</div>
                    <div className="et-head">Recovery</div>
                    <div className="et-head">Lag</div>
                    <div className="et-head">Rate</div>
                    {data.recharge_events.map((e, i) => (
                      <React.Fragment key={i}>
                        <div className="et-cell mono">{e.date}</div>
                        <div className="et-cell cyan">{e.rainfall_mm}mm</div>
                        <div className="et-cell green">+{e.recovery_m}m</div>
                        <div className="et-cell">{e.lag_hours}h</div>
                        <div className="et-cell">{e.recharge_rate_m_per_day?.toFixed(4)}m/d</div>
                      </React.Fragment>
                    ))}
                  </div>
                </>
              ) : (
                <div className="chart-empty">No recharge events detected in the analysis window.<br/>Events require ≥10mm rainfall followed by water level recovery.</div>
              )}
            </div>

            <div className="chart-card">
              <div className="cc-title">🪨 Aquifer Context</div>
              <div className="aquifer-info">
                <div className="ai-type" style={{color: '#00c8ff'}}>{data.aquifer_type}</div>
                <div className="ai-desc">
                  {data.aquifer_type === 'Alluvial'  && 'Fast recharge (6–12h lag). High permeability. Responds quickly to rainfall.'}
                  {data.aquifer_type === 'Hard Rock'  && 'Slow recharge (24–48h lag). Low permeability. Dependent on fractures.'}
                  {data.aquifer_type === 'Basalt'     && 'Moderate recharge. Vesicular basalt allows intermediate permeability.'}
                  {data.aquifer_type === 'Granite'    && 'Very slow recharge. Relies on secondary porosity and fractures.'}
                  {data.aquifer_type === 'Limestone'  && 'Variable recharge via karst features. Can be fast in karstic zones.'}
                  {!['Alluvial','Hard Rock','Basalt','Granite','Limestone'].includes(data.aquifer_type) && 'Recharge characteristics depend on local geology and fracture patterns.'}
                </div>
                {data.lag_hours > 0 && (
                  <div className="ai-lag">
                    <span>Observed lag:</span>
                    <span style={{color:'#f5c842'}}>{data.lag_hours?.toFixed(1)} hours</span>
                  </div>
                )}
                {data.recharge_capacity_m != null && (
                  <div className="ai-lag">
                    <span>Remaining capacity:</span>
                    <span style={{color:'#00e5a0'}}>{data.recharge_capacity_m?.toFixed(2)}m</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TASK 3 DETAIL PAGE
// ══════════════════════════════════════════════════════════════
export function Task3Detail({ station, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch3 = async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/task3/${station.station_id}?days=365`);
        const d = await r.json();
        setData(d.error ? null : d);
      } catch { setData(null); }
      setLoading(false);
    };
    fetch3();
  }, [station.station_id]);

  const s = STATUS[data?.status] || STATUS.unknown;

  const cgwbZones = [
    { key: 'safe',           pct: 40, label: 'Safe (< 8m)'           },
    { key: 'semi_critical',  pct: 25, label: 'Semi-Critical (8–15m)'  },
    { key: 'critical',       pct: 20, label: 'Critical (15–25m)'      },
    { key: 'over_exploited', pct: 15, label: 'Over-Exploited (> 25m)' },
  ];

  return (
    <div className="task-detail-page">
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>← Back to Station</button>
        <div className="tdp-title-row">
          <div className="tdp-tag task3-tag">Task 3</div>
          <div>
            <div className="tdp-title">Groundwater Resource Evaluation</div>
            <div className="tdp-sub">{station.station_name} · {station.district} · {station.state}</div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="tdp-loading"><div className="tdp-spinner" /><span>Evaluating groundwater resources...</span></div>
      ) : !data ? (
        <div className="tdp-empty">No evaluation data available for this station.</div>
      ) : (
        <>
          {/* Alert banner */}
          {data.alert_required && (
            <div className="alert-banner">
              🚨 <strong>CRITICAL ALERT</strong> — This station requires immediate intervention.
              Water table has reached {data.current_level_m}m depth.
            </div>
          )}

          {/* KPI row */}
          <div className="kpi-row">
            <StatCard icon="💧" label="Current Level" value={data.current_level_m?.toFixed(2) ?? '—'} unit="m" color={s.color} />
            <StatCard icon="🎯" label="RAI Score" value={data.resource_availability_index?.toFixed(1) ?? '—'} unit="/100" color={s.color} sub="Resource Availability" />
<StatCard 
  icon="📉" 
  label="Annual Depletion" 
  value={`${data.annual_depletion_rate_m > 0 ? '+' : ''}${data.annual_depletion_rate_m?.toFixed(2) ?? '-'}`} 
  unit="m/yr" 
/>            <StatCard icon="⏳" label="Years to Depletion" value={data.years_to_depletion != null ? data.years_to_depletion : '∞'} unit={data.years_to_depletion != null ? 'yrs' : ''} color={data.years_to_depletion < 10 ? '#ff2d55' : data.years_to_depletion < 25 ? '#ff6b4a' : '#00e5a0'} />
            <StatCard icon="🗂️" label="Stage of Dev" value={data.stage_of_development_pct?.toFixed(1) ?? 'N/A'} unit={data.stage_of_development_pct != null ? '%' : ''} color="#f5c842" />
            <StatCard icon="🪨" label="Aquifer" value={data.aquifer_type || '—'} unit="" color="#6a8faa" />
          </div>

          <div className="charts-row">
            {/* CGWB status gauge */}
            <div className="chart-card">
              <div className="cc-title">🏛️ CGWB Classification</div>
              <Gauge value={data.resource_availability_index || 0} max={100}
                color={s.color} label="Resource Availability Index" />
              <div className="status-display" style={{ borderColor: s.color + '40', background: s.color + '10' }}>
                <div className="sd-dot" style={{ background: s.color, boxShadow: `0 0 12px ${s.color}` }} />
                <div>
                  <div className="sd-status" style={{ color: s.color }}>{s.label}</div>
                  <div className="sd-level">Water level: {data.current_level_m}m</div>
                </div>
              </div>
            </div>

            {/* RAI breakdown pie */}
            <div className="chart-card">
              <div className="cc-title">📊 India Zone Distribution</div>
              <div className="cc-sub">National CGWB assessment breakdown</div>
              <PieChart slices={cgwbZones.map(z => ({
                label: z.label, value: z.pct, color: STATUS[z.key].color
              }))} size={140} />
              <div className="pie-legend">
                {cgwbZones.map(z => (
                  <div key={z.key} className="pl-item">
                    <span style={{ background: STATUS[z.key].color }} />
                    {z.label} — {z.pct}%
                  </div>
                ))}
              </div>
            </div>

            {/* Depletion timeline */}
            <div className="chart-card wide">
              <div className="cc-title">⏳ Depletion Projection</div>
              <div className="cc-sub">At current annual depletion rate of {data.annual_depletion_rate_m?.toFixed(3)}m/year</div>
              {data.annual_depletion_rate_m > 0 && data.current_level_m != null ? (
                <>
                  <LineChart
                    data={Array.from({ length: Math.min(30, data.years_to_depletion || 30) }, (_, i) => ({
                      year: new Date().getFullYear() + i,
                      level: parseFloat((data.current_level_m + data.annual_depletion_rate_m * i).toFixed(2)),
                    }))}
                    xKey="year" yKey="level"
                    color="#ff6b4a" label="Projected Water Level (m)" height={180} />
                  <div className="depletion-note">
                    {data.years_to_depletion != null && data.years_to_depletion < 50
                      ? `⚠️ At this rate, the well may reach critical depth by ${new Date().getFullYear() + Math.round(data.years_to_depletion)}`
                      : '✅ Depletion timeline exceeds 50 years at current rate'}
                  </div>
                </>
              ) : (
                <div className="recovering-note">
                  ✅ Water table is recovering at {Math.abs(data.annual_depletion_rate_m || 0).toFixed(3)}m/year
                </div>
              )}
            </div>
          </div>

          {/* Historical trend */}
          <div className="charts-row">
            <div className="chart-card wide">
              <div className="cc-title">📅 Historical Trend</div>
              <div className="cc-sub">Annual average water levels — {data.historical_trend?.long_term_direction?.replace(/_/g, ' ')}</div>
              {data.historical_trend?.data?.length > 1 ? (
                <LineChart
                  data={data.historical_trend.data}
                  xKey="year" yKey="avg_level_m"
                  color={s.color} label="Annual Average (m)" height={180} />
              ) : (
                <div className="chart-empty">Insufficient historical data (need 2+ years)</div>
              )}
            </div>

            {/* CGWB thresholds reference */}
            <div className="chart-card">
              <div className="cc-title">📋 CGWB Thresholds</div>
              <div className="thresholds">
                {[
                  { label: 'Safe',           range: '< 8m',   stage: '< 70%',   color: '#00e5a0', active: data.status === 'safe' },
                  { label: 'Semi-Critical',  range: '8–15m',  stage: '70–90%',  color: '#f5c842', active: data.status === 'semi_critical' },
                  { label: 'Critical',       range: '15–25m', stage: '90–100%', color: '#ff6b4a', active: data.status === 'critical' },
                  { label: 'Over-Exploited', range: '> 25m',  stage: '> 100%',  color: '#ff2d55', active: data.status === 'over_exploited' },
                ].map(t => (
                  <div key={t.label} className={`threshold-row ${t.active ? 'active' : ''}`}
                    style={{ '--tc': t.color }}>
                    <div className="tr-dot" style={{ background: t.color }} />
                    <div className="tr-label" style={{ color: t.active ? t.color : undefined }}>{t.label}</div>
                    <div className="tr-range">{t.range}</div>
                    <div className="tr-stage">{t.stage}</div>
                    {t.active && <div className="tr-you">← YOU</div>}
                  </div>
                ))}
              </div>
              <div className="summary-text" style={{ marginTop: '1rem' }}>{data.summary}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}