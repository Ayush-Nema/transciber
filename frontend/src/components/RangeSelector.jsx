import React from 'react';

function secondsToMS(sec) {
  if (sec == null || isNaN(sec)) return { m: '', s: '' };
  return { m: Math.floor(sec / 60), s: Math.floor(sec % 60) };
}

function msToSeconds(m, s) {
  const mins = parseInt(m) || 0;
  const secs = parseInt(s) || 0;
  if (!m && !s) return null;
  return mins * 60 + secs;
}

function formatDuration(sec) {
  if (sec == null || isNaN(sec)) return '';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}

function DurationInput({ value, onChange }) {
  const { m, s } = secondsToMS(value);
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <input
        type="number"
        min="0"
        placeholder="0"
        value={m}
        onChange={(e) => onChange(msToSeconds(e.target.value, s))}
        style={{ width: 52, textAlign: 'center' }}
        className="time-input"
      />
      <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>m</span>
      <input
        type="number"
        min="0"
        max="59"
        placeholder="00"
        value={s}
        onChange={(e) => onChange(msToSeconds(m, e.target.value))}
        style={{ width: 52, textAlign: 'center' }}
        className="time-input"
      />
      <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>s</span>
    </span>
  );
}

export default function RangeSelector({ duration, startTime, endTime, onStartChange, onEndChange }) {
  return (
    <div className="range-selector">
      <h3>Transcribe Segment (optional)</h3>
      <div className="range-inputs">
        <label>From:</label>
        <DurationInput value={startTime} onChange={onStartChange} />
        <label>To:</label>
        <DurationInput value={endTime} onChange={onEndChange} />
        {duration && (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Total: {formatDuration(duration)}
          </span>
        )}
      </div>
    </div>
  );
}
