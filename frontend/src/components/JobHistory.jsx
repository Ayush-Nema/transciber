import React from 'react';

export default function JobHistory({ jobs, onSelect, activeJobId }) {
  if (!jobs || jobs.length === 0) return null;

  return (
    <div className="history-list">
      <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
        Recent Jobs
      </h3>
      {jobs.map((job) => (
        <div
          key={job.id}
          className="history-item"
          onClick={() => onSelect(job)}
          style={job.id === activeJobId ? { borderColor: 'var(--accent)' } : {}}
        >
          <span className={`status-dot ${job.status}`} />
          <span className="title">{job.title || job.url}</span>
          <span className={`platform-badge ${job.platform}`}>{job.platform}</span>
        </div>
      ))}
    </div>
  );
}
