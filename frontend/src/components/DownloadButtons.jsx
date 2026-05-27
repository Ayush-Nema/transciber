import React, { useEffect, useRef, useState } from 'react';
import { api } from '../hooks/useApi';

function sanitizeFilename(name) {
  return name.replace(/[\\/:*?"<>|]+/g, '_').slice(0, 120);
}

function extFromPath(path) {
  return path?.match(/\.[^./\\]+$/)?.[0] ?? '.mp4';
}

function triggerDownload(href, filename) {
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

const buttonStyle = (busy) => ({
  padding: '5px 12px',
  background: 'var(--bg-input)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  color: 'var(--text-secondary)',
  fontSize: '0.8rem',
  cursor: busy ? 'wait' : 'pointer',
  transition: 'all 0.2s',
  fontWeight: 500,
  whiteSpace: 'nowrap',
});

export default function DownloadButtons({ jobId, title, videoPath }) {
  const [busy, setBusy] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  if (!jobId || !videoPath) return null;

  const baseName = sanitizeFilename(title?.trim() || jobId);

  const startDownload = (kind, href, filename, resetAfterMs) => {
    setBusy(kind);
    triggerDownload(href, filename);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setBusy(null), resetAfterMs);
  };

  const handleVideo = () =>
    startDownload('video', api.getVideoDownloadUrl(jobId), `${baseName}${extFromPath(videoPath)}`, 1500);

  // MP3 may need on-the-fly ffmpeg conversion; give it a moment.
  const handleMp3 = () =>
    startDownload('mp3', api.getMp3Url(jobId), `${baseName}.mp3`, 3000);

  return (
    <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
      <button
        onClick={handleVideo}
        disabled={busy != null}
        title="Download video file"
        style={buttonStyle(busy === 'video')}
      >
        {busy === 'video' ? 'Preparing...' : 'Download Video'}
      </button>
      <button
        onClick={handleMp3}
        disabled={busy != null}
        title="Download audio as MP3"
        style={buttonStyle(busy === 'mp3')}
      >
        {busy === 'mp3' ? 'Preparing...' : 'Download MP3'}
      </button>
    </div>
  );
}
