import React, { useState, useEffect, useRef } from 'react';

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export default function TranscriptionPanel({ transcription, segments, currentTime, onSeekTo }) {
  const [activeIdx, setActiveIdx] = useState(-1);
  const panelRef = useRef(null);

  // Highlight active segment based on video time
  useEffect(() => {
    if (!segments?.length || currentTime == null) return;
    const idx = segments.findIndex(
      (seg, i) => currentTime >= seg.start && (i === segments.length - 1 || currentTime < segments[i + 1]?.start)
    );
    if (idx !== -1 && idx !== activeIdx) {
      setActiveIdx(idx);
      // Auto-scroll to active segment
      const el = panelRef.current?.querySelector(`[data-seg="${idx}"]`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [currentTime, segments, activeIdx]);

  if (!transcription) {
    return (
      <div className="empty-state">
        <div className="icon">&#128196;</div>
        <p>Transcription will appear here</p>
      </div>
    );
  }

  // If we have segments, show timestamped view
  if (segments && segments.length > 0) {
    return (
      <div className="transcription-panel" ref={panelRef}>
        {segments.map((seg, i) => (
          <div
            key={i}
            data-seg={i}
            className={`segment ${i === activeIdx ? 'active' : ''}`}
            onClick={() => onSeekTo?.(seg.start)}
          >
            <span className="segment-time">{formatTime(seg.start)}</span>
            <span className="segment-text">{seg.text}</span>
          </div>
        ))}
      </div>
    );
  }

  // Fallback: plain text
  return (
    <div className="transcription-panel">
      <div className="transcription-text">{transcription}</div>
    </div>
  );
}
