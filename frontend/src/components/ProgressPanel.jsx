import React from 'react';

const STEPS = [
  { key: 'downloading', label: 'Download' },
  { key: 'extracting_audio', label: 'Extract Audio' },
  { key: 'transcribing', label: 'Transcribe' },
  { key: 'generating_mindmap', label: 'Mind Map' },
];

const STATUS_ORDER = {
  downloading: 0,
  extracting_audio: 1,
  transcribing: 2,
  generating_mindmap: 3,
  completed: 4,
  failed: -1,
};

export default function ProgressPanel({ status, progress, message, error }) {
  if (!status || status === 'pending') return null;

  const currentStep = STATUS_ORDER[status] ?? -1;

  return (
    <div className="progress-container">
      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{
            width: `${Math.min(progress, 100)}%`,
            background: error ? 'var(--error)' : undefined,
          }}
        />
      </div>

      <div className="progress-message">
        {error ? (
          <span style={{ color: 'var(--error)' }}>{error}</span>
        ) : (
          <>{message || 'Processing...'} ({Math.round(progress)}%)</>
        )}
      </div>

      <div className="progress-steps">
        {STEPS.map((step, i) => {
          let className = 'step-badge';
          if (i < currentStep) className += ' done';
          else if (i === currentStep && status !== 'completed') className += ' active';
          else if (status === 'completed') className += ' done';

          return (
            <span key={step.key} className={className}>
              {i < currentStep || status === 'completed' ? '\u2713 ' : ''}
              {step.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
