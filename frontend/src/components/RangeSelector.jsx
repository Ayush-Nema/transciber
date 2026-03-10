import React from 'react';

function secondsToHMS(sec) {
  if (sec == null || isNaN(sec)) return '';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function hmsToSeconds(str) {
  if (!str) return null;
  const parts = str.split(':').map(Number);
  if (parts.some(isNaN)) return null;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0];
}

export default function RangeSelector({ duration, startTime, endTime, onStartChange, onEndChange }) {
  return (
    <div className="range-selector">
      <h3>Transcribe Segment (optional)</h3>
      <div className="range-inputs">
        <label>From:</label>
        <input
          type="text"
          className="time-input"
          placeholder="0:00"
          value={startTime != null ? secondsToHMS(startTime) : ''}
          onChange={(e) => onStartChange(hmsToSeconds(e.target.value))}
        />
        <label>To:</label>
        <input
          type="text"
          className="time-input"
          placeholder={duration ? secondsToHMS(duration) : 'end'}
          value={endTime != null ? secondsToHMS(endTime) : ''}
          onChange={(e) => onEndChange(hmsToSeconds(e.target.value))}
        />
        {duration && (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Total: {secondsToHMS(duration)}
          </span>
        )}
      </div>
    </div>
  );
}
