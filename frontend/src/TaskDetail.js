import React, { useState, useEffect } from 'react';
import './TaskDetail.css';

const API = 'http://127.0.0.1:8000/api';

function PieChart({ slices, size = 120 }) {
  const r = size / 2 - 8, cx = size / 2, cy = size / 2;
  let cum = 0;
  const total = slices.reduce((s, sl) => s + sl.value, 0);
  if (!total) return null;
  const paths = slices.map((sl, i) => {
    const s = (cum / total) * 2 * Math.PI - Math.PI / 2;
    cum += sl.value;
    const e = (cum / total) * 2 * Math.PI - Math.PI / 2;
    const x1=cx+r*Math.cos(s), y1=cy+r*Math.sin(s);
    const x2=cx+r*Math.cos(e), y2=cy+r*Math.sin(e);
    const large = e - s > Math.PI ? 1 : 0;
    return <path key={i} d={`M${cx} ${cy} L${x1} ${y1} A${r} ${r} 0 ${large} 1 ${x2} ${y2}Z`} fill={sl.color} opacity={0.9} stroke="#030d1a" strokeWidth={1.5}/>;
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r+6} fill="#0a1f35"/>
      {paths}
      <circle cx={cx} cy={cy} r={r*0.45} fill="#030d1a"/>
    </svg>
  );
}

function LineChart({ data, xKey, yKey, color='#00c8ff', label='', height=180 }) {
  if (!data || data.length < 2) return <div className="chart-empty">Insufficient data</div>;
  const vals = data.map(d => parseFloat(d[yKey])||0);
  const labels = data.map(d => d[xKey]);
  const min=Math.min(...vals), max=Math.max(...vals), range=max-min||1;
  const W=500, H=height, pad={t:20,b:30,l:45,r:10};
  const iW=W-pad.l-pad.r, iH=H-pad.t-pad.b;
  const pts = vals.map((v,i) => [pad.l+(i/(vals.length-1))*iW, pad.t+(1-(v-min)/range)*iH]);
  const polyline = pts.map(p=>p.join(',')).join(' ');
  const area = `${pad.l},${pad.t+iH} ${polyline} ${pad.l+iW},${pad.t+iH}`;
  const ticks = [0,0.25,0.5,0.75,1].map(t=>({y:pad.t+(1-t)*iH, val:(min+t*range).toFixed(2)}));
  const step = Math.max(1, Math.floor(labels.length/6));
  const xLabels = labels.filter((_,i)=>i%step===0||i===labels.length-1);
  const gId = `lg${color.replace('#','')}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="line-chart">
      <defs>
        <linearGradient id={gId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      {ticks.map((t,i)=>(
        <g key={i}>
          <line x1={pad.l} y1={t.y} x2={pad.l+iW} y2={t.y} stroke="#0e2a42" strokeWidth={1} strokeDasharray="3,5"/>
          <text x={pad.l-6} y={t.y+4} textAnchor="end" fill="#3a5a75" fontSize="9" fontFamily="'DM Mono',monospace">{t.val}</text>
        </g>
      ))}
      <polygon points={area} fill={`url(#${gId})`}/>
      <polyline points={polyline} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round"/>
      {pts.map(([x,y],i)=><circle key={i} cx={x} cy={y} r={3} fill={color} opacity={0.7}/>)}
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r={5} fill={color} stroke="#030d1a" strokeWidth={2}/>
      {xLabels.map((lbl,i)=>{
        const idx=labels.indexOf(lbl), x=pad.l+(idx/(labels.length-1))*iW;
        return <text key={i} x={x} y={H-8} textAnchor="middle" fill="#3a5a75" fontSize="8" fontFamily="'DM Mono',monospace">{String(lbl).slice(-5)}</text>;
      })}
      <line x1={pad.l} y1={pad.t} x2={pad.l} y2={pad.t+iH} stroke="#163550" strokeWidth={1}/>
      <line x1={pad.l} y1={pad.t+iH} x2={pad.l+iW} y2={pad.t+iH} stroke="#163550" strokeWidth={1}/>
      {label && <text x={pad.l+iW/2} y={pad.t-6} textAnchor="middle" fill="#6a8faa" fontSize="10" fontFamily="'DM Mono',monospace">{label}</text>}
    </svg>
  );
}

function BarChart({ data, xKey, yKey, color='#00c8ff', height=160 }) {
  if (!data||!data.length) return <div className="chart-empty">No data</div>;
  const vals=data.map(d=>parseFloat(d[yKey])||0);
  const labels=data.map(d=>d[xKey]);
  const max=Math.max(...vals,0.1);
  const W=500,H=height,pad={t:10,b:28,l:40,r:10};
  const iW=W-pad.l-pad.r,iH=H-pad.t-pad.b;
  const bw=Math.max(4,iW/vals.length-3);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="bar-chart">
      {vals.map((v,i)=>{
        const x=pad.l+(i/vals.length)*iW+(iW/vals.length-bw)/2;
        const bh=(v/max)*iH, y=pad.t+iH-bh;
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={bh} fill={color} opacity={0.4+(v/max)*0.6} rx={2}/>
            {vals.length<=12&&<text x={x+bw/2} y={H-10} textAnchor="middle" fill="#3a5a75" fontSize="8" fontFamily="'DM Mono',monospace">{String(labels[i]).slice(-5)}</text>}
          </g>
        );
      })}
      <line x1={pad.l} y1={pad.t+iH} x2={pad.l+iW} y2={pad.t+iH} stroke="#163550" strokeWidth={1}/>
    </svg>
  );
}

// FIX: Gauge - correct large arc flag calculation
function Gauge({ value, max=100, color='#00c8ff', label='' }) {
  const pct = Math.min(1, Math.max(0, (value||0) / (max||100)));
  const angle = pct * Math.PI;
  const r=70, cx=100, cy=90;
  const endX = cx + r * Math.cos(Math.PI - angle);
  const endY = cy - r * Math.sin(angle);
  // FIX: large arc when angle > PI/2 (more than half the gauge)
  const large = angle > Math.PI / 2 ? 1 : 0;
  const displayVal = typeof value === 'number' ? (value > 999 ? value.toFixed(0) : value.toFixed(1)) : '—';
  return (
    <svg viewBox="0 0 200 110" className="gauge-chart">
      <path d={`M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${cx+r} ${cy}`} fill="none" stroke="#0e2a42" strokeWidth={14} strokeLinecap="round"/>
      {pct > 0 && <path d={`M ${cx-r} ${cy} A ${r} ${r} 0 ${large} 1 ${endX} ${endY}`} fill="none" stroke={color} strokeWidth={14} strokeLinecap="round" style={{filter:`drop-shadow(0 0 6px ${color}60)`}}/>}
      <text x={cx} y={cy-10} textAnchor="middle" fill={color} fontSize="22" fontWeight="700" fontFamily="'Syne',sans-serif">{displayVal}</text>
      <text x={cx} y={cy+8} textAnchor="middle" fill="#6a8faa" fontSize="9" fontFamily="'DM Mono',monospace">{label}</text>
    </svg>
  );
}

function StatCard({ icon, label, value, unit, color='#00c8ff', sub }) {
  return (
    <div className="stat-card" style={{'--card-color':color}}>
      <div className="sc-icon">{icon}</div>
      <div className="sc-val" style={{color}}>{value}<span className="sc-unit">{unit}</span></div>
      <div className="sc-label">{label}</div>
      {sub && <div className="sc-sub">{sub}</div>}
    </div>
  );
}

const STATUS = {
  safe:           {label:'Safe',          color:'#00e5a0'},
  semi_critical:  {label:'Semi-Critical', color:'#f5c842'},
  critical:       {label:'Critical',      color:'#ff6b4a'},
  over_exploited: {label:'Over-Exploited',color:'#ff2d55'},
  unknown:        {label:'Unknown',       color:'#4a6fa5'},
};

// ══════════════════════════════════════════════════════════════
// TASK 1 DETAIL
// ══════════════════════════════════════════════════════════════
export function Task1Detail({ station, onBack }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [hours, setHours]   = useState(720);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/task1/${station.station_id}?hours=${hours}`)
      .then(r=>r.json())
      .then(d=>{ setData(d.error?null:d); setLoading(false); })
      .catch(()=>{ setData(null); setLoading(false); });
  }, [station.station_id, hours]);

  const trendColor = data?.trend_direction==='falling'?'#00e5a0':data?.trend_direction==='rising'?'#ff6b4a':'#f5c842';
  const anomalyTypes = (data?.anomalies||[]).reduce((acc,a)=>({...acc,[a.type]:(acc[a.type]||0)+1}),{});

  return (
    <div className="task-detail-page">
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>← Back to Station</button>
        <div className="tdp-title-row">
          <div className="tdp-tag task1-tag">Task 1</div>
          <div><div className="tdp-title">Water Level Fluctuation Analysis</div><div className="tdp-sub">{station.station_name} · {station.district} · {station.state}</div></div>
        </div>
      </div>
      <div className="window-selector">
        <span className="ws-label">Analysis window:</span>
        {[{label:'24h',val:24},{label:'7 days',val:168},{label:'30 days',val:720},{label:'1 year',val:8760}].map(w=>(
          <button key={w.val} className={`ws-btn ${hours===w.val?'active':''}`} onClick={()=>setHours(w.val)}>{w.label}</button>
        ))}
      </div>
      {loading ? (
        <div className="tdp-loading"><div className="tdp-spinner"/><span>Running fluctuation analysis...</span></div>
      ) : !data ? (
        <div className="tdp-empty">No fluctuation data available for this station.<br/>Try expanding the time window above.</div>
      ) : (<>
        <div className="kpi-row">
          <StatCard icon="💧" label="Current Level" value={data.current_level_m?.toFixed(2)??'—'} unit="m" color="#00c8ff" sub={data.as_of?.slice(0,10)}/>
          <StatCard icon="⏱️" label="Rate / Hour" value={`${data.rate_per_hour>0?'+':''}${(data.rate_per_hour||0).toFixed(4)}`} unit="m" color={data.rate_per_hour>0?'#ff6b4a':'#00e5a0'}/>
          <StatCard icon="📅" label="Rate / Day" value={`${data.rate_per_day>0?'+':''}${(data.rate_per_day||0).toFixed(3)}`} unit="m" color={data.rate_per_day>0?'#ff6b4a':'#00e5a0'}/>
          <StatCard icon="📆" label="Rate / Week" value={`${data.rate_per_week>0?'+':''}${(data.rate_per_week||0).toFixed(3)}`} unit="m" color={data.rate_per_week>0?'#ff6b4a':'#00e5a0'}/>
          <StatCard icon="🌊" label="Season" value={data.seasonal_phase?.replace('_',' ')??'—'} unit="" color="#f5c842"/>
          <StatCard icon="⚠️" label="Anomalies" value={data.anomalies?.length??0} unit="" color={data.anomalies?.length>0?'#ff6b4a':'#00e5a0'}/>
        </div>
        <div className="charts-row">
          <div className="chart-card wide">
            <div className="cc-title">📈 30-Day Moving Average Trend</div>
            <div className="cc-sub">Daily average water level (metres depth from surface)</div>
            <LineChart data={data.moving_average||[]} xKey="date" yKey="avg_level_m" color="#00c8ff" label="Water Level (m)" height={200}/>
          </div>
          <div className="chart-card">
            <div className="cc-title">🎯 Trend Status</div>
            <Gauge value={Math.abs(data.trend_magnitude||0)} max={5} color={trendColor} label="7-day change (m)"/>
            <div className="trend-pill" style={{background:trendColor+'20',color:trendColor,borderColor:trendColor+'40'}}>
              {data.trend_direction==='rising'&&'↑ Rising — water table deepening'}
              {data.trend_direction==='falling'&&'↓ Falling — water table recovering'}
              {data.trend_direction==='stable'&&'→ Stable — no significant change'}
              {(!data.trend_direction||data.trend_direction==='unknown')&&'— Insufficient data'}
            </div>
            <div className="status-pill-large" style={{background:data.status==='recovering'?'#00e5a020':'#ff6b4a20',color:data.status==='recovering'?'#00e5a0':'#ff6b4a',borderColor:data.status==='recovering'?'#00e5a040':'#ff6b4a40'}}>
              {(data.status||'unknown').replace(/_/g,' ').toUpperCase()}
            </div>
          </div>
        </div>
        <div className="charts-row">
          <div className="chart-card">
            <div className="cc-title">📊 Rate of Change Comparison</div>
            <BarChart data={[{period:'/hr',rate:Math.abs(data.rate_per_hour||0)},{period:'/day',rate:Math.abs(data.rate_per_day||0)},{period:'/week',rate:Math.abs(data.rate_per_week||0)}]} xKey="period" yKey="rate" color={trendColor} height={140}/>
          </div>
          <div className="chart-card">
            <div className="cc-title">🔍 Anomaly Breakdown</div>
            {data.anomalies?.length>0?(<>
              <PieChart slices={[{label:'Sudden Drop',value:anomalyTypes.sudden_drop||0,color:'#ff2d55'},{label:'Statistical',value:anomalyTypes.statistical||0,color:'#f5c842'}]} size={130}/>
              <div className="pie-legend">
                <div className="pl-item"><span style={{background:'#ff2d55'}}/> Sudden drop ({anomalyTypes.sudden_drop||0})</div>
                <div className="pl-item"><span style={{background:'#f5c842'}}/> Statistical ({anomalyTypes.statistical||0})</div>
              </div>
            </>):(<div className="no-anomaly">✅ No anomalies detected in this window</div>)}
          </div>
          <div className="chart-card">
            <div className="cc-title">📋 Summary</div>
            <div className="summary-stats">
              <div className="ss-item"><span className="ss-val">{(data.total_readings||0).toLocaleString()}</span><span className="ss-lbl">Total readings</span></div>
              <div className="ss-item"><span className="ss-val">{(data.trend_magnitude||0).toFixed(3)}m</span><span className="ss-lbl">7-day change</span></div>
              <div className="ss-item"><span className="ss-val">{(data.seasonal_phase||'').replace('_',' ')}</span><span className="ss-lbl">Season</span></div>
            </div>
            <div className="summary-text">{data.summary||'Analysis complete.'}</div>
          </div>
        </div>
        {data.anomalies?.length>0&&(
          <div className="anomaly-table">
            <div className="at-title">⚠️ Anomaly Event Log</div>
            <div className="at-grid">
              <div className="at-head">Timestamp</div><div className="at-head">Type</div><div className="at-head">Magnitude</div><div className="at-head">Reason</div>
              {data.anomalies.map((a,i)=>(
                <React.Fragment key={i}>
                  <div className="at-cell mono">{a.timestamp?.slice(0,16)}</div>
                  <div className="at-cell"><span className={`at-type ${a.type}`}>{(a.type||'').replace('_',' ')}</span></div>
                  <div className="at-cell mono">{(a.magnitude_m||0).toFixed(3)}m</div>
                  <div className="at-cell text2">{a.reason}</div>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
      </>)}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TASK 2 DETAIL
// ══════════════════════════════════════════════════════════════
export function Task2Detail({ station, onBack }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/task2/${station.station_id}?days=365`)
      .then(r=>r.json())
      .then(d=>{ setData(d.error?null:d); setLoading(false); })
      .catch(()=>{ setData(null); setLoading(false); });
  }, [station.station_id]);

  const zoneColor = {good_recharge:'#00e5a0',moderate_recharge:'#f5c842',stressed:'#ff6b4a',critically_stressed:'#ff2d55',insufficient_data:'#4a6fa5'}[data?.zone_status]||'#4a6fa5';

  return (
    <div className="task-detail-page">
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>← Back to Station</button>
        <div className="tdp-title-row">
          <div className="tdp-tag task2-tag">Task 2</div>
          <div><div className="tdp-title">Dynamic Recharge Estimation</div><div className="tdp-sub">{station.station_name} · {station.district} · {station.state}</div></div>
        </div>
      </div>
      {loading ? (
        <div className="tdp-loading"><div className="tdp-spinner"/><span>Computing recharge estimates...</span></div>
      ) : !data ? (
        <div className="tdp-empty">No recharge data available.<br/>Task 2 requires rainfall data correlated with water level readings.<br/>Seed rainfall data by running: <code>python scraper.py --source sample --once</code></div>
      ) : (<>
        <div className="kpi-row">
          <StatCard icon="💧" label="Recharge Rate" value={(data.recharge_rate_m_per_day||0).toFixed(4)} unit="m/day" color="#00c8ff"/>
          <StatCard icon="⏱️" label="Lag Time" value={(data.lag_hours||0).toFixed(1)} unit="hrs" color="#f5c842" sub="Rain → response"/>
          <StatCard icon="🌧️" label="Net Recharge" value={data.net_recharge_m!=null?`${data.net_recharge_m>0?'+':''}${data.net_recharge_m}`:'—'} unit="m" color={data.net_recharge_m>0?'#00e5a0':'#ff6b4a'} sub="post − pre monsoon"/>
          <StatCard icon="📍" label="Pre-Monsoon" value={data.pre_monsoon_level_m?.toFixed(2)??'—'} unit="m" color="#6a8faa"/>
          <StatCard icon="📍" label="Post-Monsoon" value={data.post_monsoon_level_m?.toFixed(2)??'—'} unit="m" color="#00c8ff"/>
          <StatCard icon="🪨" label="Aquifer" value={data.aquifer_type||'—'} unit="" color="#f5c842"/>
        </div>
        <div className="charts-row">
          <div className="chart-card">
            <div className="cc-title">🎯 Zone Classification</div>
            <Gauge value={(data.recharge_rate_m_per_day||0)*1000} max={200} color={zoneColor} label="recharge (mm/day)"/>
            <div className="zone-badge-large" style={{background:zoneColor+'20',color:zoneColor,borderColor:zoneColor+'50'}}>{(data.zone_status||'unknown').replace(/_/g,' ').toUpperCase()}</div>
            <div className="zone-desc">
              {data.zone_status==='good_recharge'&&'Aquifer actively recharging. Extraction within sustainable limits.'}
              {data.zone_status==='moderate_recharge'&&'Some recovery observed but below expected seasonal norms.'}
              {data.zone_status==='stressed'&&'Minimal recharge detected. Monitor closely.'}
              {data.zone_status==='critically_stressed'&&'Zero or negative net recharge. Immediate action needed.'}
              {data.zone_status==='insufficient_data'&&'Insufficient seasonal data for classification.'}
            </div>
          </div>
          <div className="chart-card wide">
            <div className="cc-title">🌦️ Pre vs Post Monsoon Water Levels</div>
            <div className="cc-sub">Lower value = deeper water table</div>
            {data.pre_monsoon_level_m!=null&&data.post_monsoon_level_m!=null?(<>
              <BarChart data={[{period:'Pre-Monsoon',level:data.pre_monsoon_level_m},{period:'Post-Monsoon',level:data.post_monsoon_level_m}]} xKey="period" yKey="level" color="#00c8ff" height={150}/>
              <div className="monsoon-compare">
                <div className="mc-item"><span className="mc-label">Pre-monsoon</span><span className="mc-val" style={{color:'#f5c842'}}>{data.pre_monsoon_level_m?.toFixed(3)}m</span></div>
                <div className="mc-arrow" style={{color:data.net_recharge_m>0?'#00e5a0':'#ff6b4a'}}>{data.net_recharge_m>0?'↓ Improved':'↑ Worsened'} by {Math.abs(data.net_recharge_m||0).toFixed(3)}m</div>
                <div className="mc-item"><span className="mc-label">Post-monsoon</span><span className="mc-val" style={{color:'#00c8ff'}}>{data.post_monsoon_level_m?.toFixed(3)}m</span></div>
              </div>
            </>):(<div className="chart-empty">Monsoon season data not yet available in DB.<br/>This station needs readings spanning Jun–Nov for pre/post monsoon comparison.</div>)}
          </div>
        </div>
        <div className="charts-row">
          <div className="chart-card wide">
            <div className="cc-title">⚡ Recharge Events (Last 10)</div>
            <div className="cc-sub">Individual rainfall → water level recovery events</div>
            {data.recharge_events?.length>0?(<>
              <LineChart data={[...data.recharge_events].reverse()} xKey="date" yKey="recovery_m" color="#00e5a0" label="Recovery (m)" height={160}/>
              <div className="events-table">
                <div className="et-head">Date</div><div className="et-head">Rainfall</div><div className="et-head">Recovery</div><div className="et-head">Lag</div><div className="et-head">Rate</div>
                {data.recharge_events.map((e,i)=>(
                  <React.Fragment key={i}>
                    <div className="et-cell mono">{e.date}</div>
                    <div className="et-cell cyan">{e.rainfall_mm}mm</div>
                    <div className="et-cell green">+{e.recovery_m}m</div>
                    <div className="et-cell">{e.lag_hours}h</div>
                    <div className="et-cell">{(e.recharge_rate_m_per_day||0).toFixed(4)}m/d</div>
                  </React.Fragment>
                ))}
              </div>
            </>):(<div className="chart-empty">No recharge events detected.<br/>Events require ≥10mm rainfall followed by measurable water level recovery.</div>)}
          </div>
          <div className="chart-card">
            <div className="cc-title">🪨 Aquifer Context</div>
            <div className="aquifer-info">
              <div className="ai-type" style={{color:'#00c8ff'}}>{data.aquifer_type||'Unknown'}</div>
              <div className="ai-desc">
                {data.aquifer_type==='Alluvial'&&'Fast recharge (6–12h lag). High permeability. Responds quickly to rainfall.'}
                {data.aquifer_type==='Hard Rock'&&'Slow recharge (24–48h lag). Low permeability. Dependent on fractures.'}
                {data.aquifer_type==='Basalt'&&'Moderate recharge. Vesicular basalt allows intermediate permeability.'}
                {data.aquifer_type==='Granite'&&'Very slow recharge. Relies on secondary porosity and fractures.'}
                {data.aquifer_type==='Limestone'&&'Variable recharge via karst features. Can be fast in karstic zones.'}
                {!['Alluvial','Hard Rock','Basalt','Granite','Limestone'].includes(data.aquifer_type)&&'Recharge characteristics depend on local geology and fracture patterns.'}
              </div>
              {data.lag_hours>0&&<div className="ai-lag"><span>Observed lag:</span><span style={{color:'#f5c842'}}>{data.lag_hours?.toFixed(1)} hours</span></div>}
              {data.recharge_capacity_m!=null&&<div className="ai-lag"><span>Remaining capacity:</span><span style={{color:'#00e5a0'}}>{data.recharge_capacity_m?.toFixed(2)}m</span></div>}
            </div>
          </div>
        </div>
      </>)}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// TASK 3 DETAIL
// ══════════════════════════════════════════════════════════════
export function Task3Detail({ station, onBack }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/task3/${station.station_id}?days=365`)
      .then(r=>r.json())
      .then(d=>{ setData(d.error?null:d); setLoading(false); })
      .catch(()=>{ setData(null); setLoading(false); });
  }, [station.station_id]);

  const s = STATUS[data?.status]||STATUS.unknown;
  const cgwbZones = [
    {key:'safe',pct:40,label:'Safe (< 8m)'},
    {key:'semi_critical',pct:25,label:'Semi-Critical (8–15m)'},
    {key:'critical',pct:20,label:'Critical (15–25m)'},
    {key:'over_exploited',pct:15,label:'Over-Exploited (> 25m)'},
  ];

  // FIX: compute depletion display as string before JSX
  const deplRate = data?.annual_depletion_rate_m;
  const deplDisplay = deplRate != null ? `${deplRate > 0 ? '+' : ''}${deplRate.toFixed(3)}` : '—';
  const deplColor = deplRate != null ? (deplRate > 0 ? '#ff6b4a' : '#00e5a0') : '#6a8faa';

  return (
    <div className="task-detail-page">
      <div className="tdp-header">
        <button className="back-btn" onClick={onBack}>← Back to Station</button>
        <div className="tdp-title-row">
          <div className="tdp-tag task3-tag">Task 3</div>
          <div><div className="tdp-title">Groundwater Resource Evaluation</div><div className="tdp-sub">{station.station_name} · {station.district} · {station.state}</div></div>
        </div>
      </div>
      {loading ? (
        <div className="tdp-loading"><div className="tdp-spinner"/><span>Evaluating groundwater resources...</span></div>
      ) : !data ? (
        <div className="tdp-empty">No evaluation data available for this station.</div>
      ) : (<>
        {data.alert_required&&(
          <div className="alert-banner">🚨 <strong>CRITICAL ALERT</strong> — Immediate intervention required. Water table at {data.current_level_m}m depth.</div>
        )}
        <div className="kpi-row">
          <StatCard icon="💧" label="Current Level" value={data.current_level_m?.toFixed(2)??'—'} unit="m" color={s.color}/>
          <StatCard icon="🎯" label="RAI Score" value={data.resource_availability_index?.toFixed(1)??'—'} unit="/100" color={s.color} sub="Resource Availability"/>
          <StatCard icon="📉" label="Annual Depletion" value={deplDisplay} unit="m/yr" color={deplColor}/>
          <StatCard icon="⏳" label="Years to Depletion" value={data.years_to_depletion!=null?data.years_to_depletion:'∞'} unit={data.years_to_depletion!=null?'yrs':''} color={data.years_to_depletion!=null&&data.years_to_depletion<10?'#ff2d55':data.years_to_depletion!=null&&data.years_to_depletion<25?'#ff6b4a':'#00e5a0'}/>
          <StatCard icon="🗂️" label="Stage of Dev" value={data.stage_of_development_pct!=null?data.stage_of_development_pct.toFixed(1):'N/A'} unit={data.stage_of_development_pct!=null?'%':''} color="#f5c842"/>
          <StatCard icon="🪨" label="Aquifer" value={data.aquifer_type||'—'} unit="" color="#6a8faa"/>
        </div>
        <div className="charts-row">
          <div className="chart-card">
            <div className="cc-title">🏛️ CGWB Classification</div>
            <Gauge value={data.resource_availability_index||0} max={100} color={s.color} label="Resource Availability Index"/>
            <div className="status-display" style={{borderColor:s.color+'40',background:s.color+'10'}}>
              <div className="sd-dot" style={{background:s.color,boxShadow:`0 0 12px ${s.color}`}}/>
              <div><div className="sd-status" style={{color:s.color}}>{s.label}</div><div className="sd-level">Water level: {data.current_level_m}m</div></div>
            </div>
          </div>
          <div className="chart-card">
            <div className="cc-title">📊 India Zone Distribution</div>
            <div className="cc-sub">National CGWB assessment breakdown</div>
            <PieChart slices={cgwbZones.map(z=>({label:z.label,value:z.pct,color:STATUS[z.key].color}))} size={140}/>
            <div className="pie-legend">
              {cgwbZones.map(z=><div key={z.key} className="pl-item"><span style={{background:STATUS[z.key].color}}/>{z.label} — {z.pct}%</div>)}
            </div>
          </div>
          <div className="chart-card wide">
            <div className="cc-title">⏳ Depletion Projection</div>
            <div className="cc-sub">At current annual rate of {deplDisplay}m/year</div>
            {deplRate != null && deplRate > 0 && data.current_level_m != null ? (<>
              <LineChart
                data={Array.from({length:Math.min(30,Math.ceil(data.years_to_depletion||30))},(_, i)=>({
                  year: new Date().getFullYear()+i,
                  level: parseFloat((data.current_level_m+deplRate*i).toFixed(2)),
                }))}
                xKey="year" yKey="level" color="#ff6b4a" label="Projected Water Level (m)" height={180}/>
              <div className="depletion-note">
                {data.years_to_depletion!=null&&data.years_to_depletion<50
                  ?`⚠️ At this rate, may reach critical depth by ${new Date().getFullYear()+Math.round(data.years_to_depletion)}`
                  :'✅ Depletion timeline exceeds 50 years at current rate'}
              </div>
            </>):(
              <div className="recovering-note">✅ Water table recovering at {Math.abs(deplRate||0).toFixed(3)}m/year — no depletion projected</div>
            )}
          </div>
        </div>
        <div className="charts-row">
          <div className="chart-card wide">
            <div className="cc-title">📅 Historical Trend</div>
            <div className="cc-sub">Annual average water levels — {(data.historical_trend?.long_term_direction||'').replace(/_/g,' ')}</div>
            {data.historical_trend?.data?.length>1
              ?<LineChart data={data.historical_trend.data} xKey="year" yKey="avg_level_m" color={s.color} label="Annual Average (m)" height={180}/>
              :<div className="chart-empty">Insufficient historical data (need 2+ years of readings)</div>}
          </div>
          <div className="chart-card">
            <div className="cc-title">📋 CGWB Thresholds</div>
            <div className="thresholds">
              {[
                {label:'Safe',          range:'< 8m',   stage:'< 70%',   color:'#00e5a0',key:'safe'},
                {label:'Semi-Critical', range:'8–15m',  stage:'70–90%',  color:'#f5c842',key:'semi_critical'},
                {label:'Critical',      range:'15–25m', stage:'90–100%', color:'#ff6b4a',key:'critical'},
                {label:'Over-Exploited',range:'> 25m',  stage:'> 100%',  color:'#ff2d55',key:'over_exploited'},
              ].map(t=>(
                <div key={t.key} className={`threshold-row ${data.status===t.key?'active':''}`} style={{'--tc':t.color}}>
                  <div className="tr-dot" style={{background:t.color}}/>
                  <div className="tr-label" style={{color:data.status===t.key?t.color:undefined}}>{t.label}</div>
                  <div className="tr-range">{t.range}</div>
                  <div className="tr-stage">{t.stage}</div>
                  {data.status===t.key&&<div className="tr-you">← YOU</div>}
                </div>
              ))}
            </div>
            <div className="summary-text" style={{marginTop:'1rem'}}>{data.summary}</div>
          </div>
        </div>
      </>)}
    </div>
  );
}