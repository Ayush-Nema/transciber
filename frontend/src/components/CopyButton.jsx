import React, { useState } from 'react';

export default function CopyButton({ getText, label = 'Copy Text' }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(getText());
    } catch {
      const ta = document.createElement('textarea');
      ta.value = getText();
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      title={label}
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
      {copied ? 'Copied!' : label}
    </button>
  );
}
