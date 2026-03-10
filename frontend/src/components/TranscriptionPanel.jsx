import React, { useState, useEffect, useRef } from 'react';

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export default function TranscriptionPanel({ transcription, segments, currentTime, onSeekTo }) {
  const [viewMode, setViewMode] = useState('paragraph'); // 'paragraph' | 'timestamps'
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
      // Auto-scroll to active segment in timestamp view
      if (viewMode === 'timestamps') {
        const el = panelRef.current?.querySelector(`[data-seg="${idx}"]`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    }
  }, [currentTime, segments, activeIdx, viewMode]);

  if (!transcription) {
    return (
      <div className="empty-state">
        <div className="icon">&#128196;</div>
        <p>Transcription will appear here</p>
      </div>
    );
  }

  const hasSegments = segments && segments.length > 0;

  return (
    <div className="transcription-panel" ref={panelRef}>
      {/* View mode toggle */}
      {hasSegments && (
        <div style={{
          display: 'flex',
          gap: 16,
          padding: '8px 0 12px',
          borderBottom: '1px solid var(--border)',
          marginBottom: 12,
        }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            cursor: 'pointer',
            fontSize: '0.85rem',
            color: viewMode === 'paragraph' ? 'var(--accent)' : 'var(--text-secondary)',
          }}>
            <input
              type="radio"
              name="viewMode"
              value="paragraph"
              checked={viewMode === 'paragraph'}
              onChange={() => setViewMode('paragraph')}
              style={{ accentColor: 'var(--accent)' }}
            />
            Paragraph
          </label>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            cursor: 'pointer',
            fontSize: '0.85rem',
            color: viewMode === 'timestamps' ? 'var(--accent)' : 'var(--text-secondary)',
          }}>
            <input
              type="radio"
              name="viewMode"
              value="timestamps"
              checked={viewMode === 'timestamps'}
              onChange={() => setViewMode('timestamps')}
              style={{ accentColor: 'var(--accent)' }}
            />
            Timestamps
          </label>
        </div>
      )}

      {/* Paragraph view (default) */}
      {(!hasSegments || viewMode === 'paragraph') && (
        <div className="transcription-text" style={{
          lineHeight: 1.8,
          fontSize: '0.95rem',
          whiteSpace: 'pre-wrap',
          color: 'var(--text-primary)',
        }}>
          {transcription}
        </div>
      )}

      {/* Timestamp view */}
      {hasSegments && viewMode === 'timestamps' && (
        <div>
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
      )}
    </div>
  );
}
