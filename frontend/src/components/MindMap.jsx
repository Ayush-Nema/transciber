import React, { useState, useMemo } from 'react';

/**
 * Interactive mind-map component.
 * Expects mindmapData as a JSON string with structure:
 * { title: string, themes: [{ label: string, points: [{ text: string, detail?: string }] }] }
 *
 * Falls back to showing raw text if the data can't be parsed as JSON
 * (backward compat with old Mermaid strings).
 */

// Color palette for theme branches
const THEME_COLORS = [
  { bg: 'rgba(108, 92, 231, 0.15)', border: '#6c5ce7', text: '#a29bfe' },
  { bg: 'rgba(0, 184, 148, 0.15)', border: '#00b894', text: '#55efc4' },
  { bg: 'rgba(253, 203, 110, 0.15)', border: '#fdcb6e', text: '#ffeaa7' },
  { bg: 'rgba(225, 112, 85, 0.15)', border: '#e17055', text: '#fab1a0' },
  { bg: 'rgba(116, 185, 255, 0.15)', border: '#74b9ff', text: '#74b9ff' },
  { bg: 'rgba(162, 155, 254, 0.15)', border: '#a29bfe', text: '#a29bfe' },
];

function CopyButton({ getText, label = 'Copy' }) {
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
      style={{
        padding: '6px 14px',
        background: copied ? 'rgba(0,184,148,0.2)' : 'var(--bg-input)',
        border: `1px solid ${copied ? 'var(--success)' : 'var(--border)'}`,
        borderRadius: 8,
        color: copied ? 'var(--success)' : 'var(--text-secondary)',
        fontSize: '0.8rem',
        cursor: 'pointer',
        transition: 'all 0.2s',
        fontWeight: 500,
      }}
    >
      {copied ? 'Copied!' : label}
    </button>
  );
}

function ThemeCard({ theme, colorIdx, defaultExpanded }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const color = THEME_COLORS[colorIdx % THEME_COLORS.length];

  return (
    <div style={{
      background: color.bg,
      border: `1px solid ${color.border}`,
      borderRadius: 12,
      overflow: 'hidden',
      transition: 'all 0.2s',
    }}>
      {/* Theme header */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '12px 16px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          userSelect: 'none',
        }}
      >
        <span style={{
          fontSize: '0.75rem',
          transition: 'transform 0.2s',
          transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
          color: color.text,
        }}>
          &#9654;
        </span>
        <span style={{
          fontWeight: 600,
          fontSize: '0.95rem',
          color: color.text,
        }}>
          {theme.label}
        </span>
        <span style={{
          marginLeft: 'auto',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
        }}>
          {theme.points?.length || 0} points
        </span>
      </div>

      {/* Points */}
      {expanded && theme.points?.length > 0 && (
        <div style={{
          padding: '0 16px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}>
          {theme.points.map((point, pi) => (
            <div
              key={pi}
              style={{
                padding: '8px 12px',
                background: 'rgba(0,0,0,0.15)',
                borderRadius: 8,
                borderLeft: `3px solid ${color.border}`,
              }}
            >
              <div style={{
                fontSize: '0.9rem',
                color: 'var(--text-primary)',
                lineHeight: 1.5,
              }}>
                {point.text}
              </div>
              {point.detail && (
                <div style={{
                  fontSize: '0.8rem',
                  color: 'var(--text-secondary)',
                  marginTop: 4,
                  lineHeight: 1.4,
                  fontStyle: 'italic',
                }}>
                  {point.detail}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function MindMap({ mermaidCode: mindmapData }) {
  // Parse the JSON data (prop name kept as mermaidCode for backward compat)
  const parsed = useMemo(() => {
    if (!mindmapData) return null;

    try {
      const data = JSON.parse(mindmapData);
      if (data.themes && Array.isArray(data.themes)) {
        return data;
      }
      return null;
    } catch {
      // Not JSON — old Mermaid format, show as raw text
      return null;
    }
  }, [mindmapData]);

  // Generate plain-text version for copying
  const getPlainText = () => {
    if (!parsed) return mindmapData || '';

    let lines = [`# ${parsed.title}`, ''];
    parsed.themes.forEach((theme, i) => {
      lines.push(`## ${i + 1}. ${theme.label}`);
      theme.points?.forEach((point, j) => {
        lines.push(`  ${j + 1}. ${point.text}`);
        if (point.detail) {
          lines.push(`     - ${point.detail}`);
        }
      });
      lines.push('');
    });
    return lines.join('\n');
  };

  if (!mindmapData) {
    return (
      <div className="empty-state">
        <div className="icon">&#128506;</div>
        <p>Mind map will be generated after transcription</p>
      </div>
    );
  }

  // Fallback for old Mermaid-format data
  if (!parsed) {
    return (
      <div style={{ padding: 16 }}>
        <pre style={{
          background: 'var(--bg-input)',
          padding: 16,
          borderRadius: 8,
          fontSize: '0.85rem',
          overflow: 'auto',
          maxHeight: 400,
          color: 'var(--text-primary)',
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
        }}>
          {mindmapData}
        </pre>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header with title + copy */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 4px',
      }}>
        <h3 style={{
          fontSize: '1.1rem',
          fontWeight: 700,
          color: 'var(--text-primary)',
          margin: 0,
        }}>
          {parsed.title}
        </h3>
        <CopyButton getText={getPlainText} label="Copy Mind Map" />
      </div>

      {/* Theme cards */}
      {parsed.themes.length === 0 ? (
        <div className="empty-state">
          <p>No themes extracted from the transcription</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {parsed.themes.map((theme, i) => (
            <ThemeCard
              key={i}
              theme={theme}
              colorIdx={i}
              defaultExpanded={i < 3}
            />
          ))}
        </div>
      )}

      {/* Summary footer */}
      <div style={{
        fontSize: '0.78rem',
        color: 'var(--text-muted)',
        textAlign: 'center',
        paddingTop: 4,
      }}>
        {parsed.themes.length} themes &middot;{' '}
        {parsed.themes.reduce((sum, t) => sum + (t.points?.length || 0), 0)} key points
      </div>
    </div>
  );
}
