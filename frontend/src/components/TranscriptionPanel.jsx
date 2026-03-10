import React, { useState, useEffect, useRef } from 'react';

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function CopyButton({ getText }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(getText());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = getText();
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      title="Copy transcription to clipboard"
      style={{
        padding: '5px 12px',
        background: copied ? 'rgba(0,184,148,0.2)' : 'var(--bg-input)',
        border: `1px solid ${copied ? 'var(--success)' : 'var(--border)'}`,
        borderRadius: 8,
        color: copied ? 'var(--success)' : 'var(--text-secondary)',
        fontSize: '0.8rem',
        cursor: 'pointer',
        transition: 'all 0.2s',
        fontWeight: 500,
        whiteSpace: 'nowrap',
      }}
    >
      {copied ? 'Copied!' : 'Copy Text'}
    </button>
  );
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
      if (viewMode === 'timestamps') {
        const el = panelRef.current?.querySelector(`[data-seg="${idx}"]`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    }
  }, [currentTime, segments, activeIdx, viewMode]);

  // Build copy text based on current view mode
  const getCopyText = () => {
    if (viewMode === 'timestamps' && segments?.length) {
      return segments.map(seg => `[${formatTime(seg.start)}] ${seg.text}`).join('\n');
    }
    return transcription || '';
  };

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
      {/* Toolbar: view toggle + copy */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '8px 0 12px',
        borderBottom: '1px solid var(--border)',
        marginBottom: 12,
      }}>
        {hasSegments && (
          <>
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
          </>
        )}
        <div style={{ marginLeft: 'auto' }}>
          <CopyButton getText={getCopyText} />
        </div>
      </div>

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
