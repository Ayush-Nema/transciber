import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  mindmap: {
    padding: 20,
    useMaxWidth: true,
  },
  themeVariables: {
    primaryColor: '#6c5ce7',
    primaryTextColor: '#e8eaed',
    primaryBorderColor: '#333845',
    lineColor: '#555',
    secondaryColor: '#2a2e3a',
    tertiaryColor: '#1a1d27',
  },
});

export default function MindMap({ mermaidCode }) {
  const containerRef = useRef(null);
  const [error, setError] = useState(null);
  const [rawVisible, setRawVisible] = useState(false);

  useEffect(() => {
    if (!mermaidCode || !containerRef.current) return;
    setError(null);

    const render = async () => {
      try {
        containerRef.current.innerHTML = '';
        const id = `mindmap-${Date.now()}`;
        const { svg } = await mermaid.render(id, mermaidCode);
        containerRef.current.innerHTML = svg;
      } catch (err) {
        console.error('Mermaid render error:', err);
        setError(err.message);
      }
    };

    render();
  }, [mermaidCode]);

  if (!mermaidCode) {
    return (
      <div className="empty-state">
        <div className="icon">&#128506;</div>
        <p>Mind map will be generated after transcription</p>
      </div>
    );
  }

  return (
    <div>
      {error && (
        <div className="error-banner">
          Mind map rendering error: {error}
          <button className="btn btn-sm btn-secondary" style={{ marginLeft: 12 }} onClick={() => setRawVisible(!rawVisible)}>
            {rawVisible ? 'Hide' : 'Show'} Raw Code
          </button>
        </div>
      )}
      {rawVisible && (
        <pre style={{
          background: 'var(--bg-input)',
          padding: 12,
          borderRadius: 8,
          fontSize: '0.8rem',
          overflow: 'auto',
          maxHeight: 200,
          marginBottom: 12,
        }}>
          {mermaidCode}
        </pre>
      )}
      <div className="mindmap-container" ref={containerRef} />
    </div>
  );
}
