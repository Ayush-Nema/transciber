import React, { useState, useRef, useEffect } from 'react';
import VideoPlayer from './components/VideoPlayer';
import ProgressPanel from './components/ProgressPanel';
import TranscriptionPanel from './components/TranscriptionPanel';
import RangeSelector from './components/RangeSelector';
import DownloadButtons from './components/DownloadButtons';
import { api } from './hooks/useApi';
import { useSSE } from './hooks/useSSE';

export default function App() {
  // ── State ──
  const [url, setUrl] = useState('');
  const [asrProvider, setAsrProvider] = useState('openai');
  const [language, setLanguage] = useState('auto');
  const [startTime, setStartTime] = useState(null);
  const [endTime, setEndTime] = useState(null);
  const [splitDuration, setSplitDuration] = useState('');
  const [context, setContext] = useState('');
  const [llmCleanup, setLlmCleanup] = useState(true);

  const [currentJob, setCurrentJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetchingInfo, setFetchingInfo] = useState(false);
  const [error, setError] = useState(null);

  const [videoTime, setVideoTime] = useState(0);

  const videoRef = useRef(null);

  // ── SSE Subscription ──
  const { latestEvent, isDone, reset: resetSSE } = useSSE(
    currentJob?.id && currentJob.status !== 'completed' && currentJob.status !== 'failed'
      ? currentJob.id
      : null
  );

  // Update job from SSE events
  useEffect(() => {
    if (!latestEvent) return;
    const { type, data } = latestEvent;

    setCurrentJob(prev => {
      if (!prev) return prev;
      const updates = { ...prev };

      if (data.progress != null) updates.progress = data.progress;
      if (data.message) updates.progress_message = data.message;

      if (type === 'downloading') updates.status = 'downloading';
      else if (type === 'extracting_audio') updates.status = 'extracting_audio';
      else if (type === 'transcribing') updates.status = 'transcribing';
      else if (type === 'completed') {
        updates.status = 'completed';
        updates.progress = 100;
        if (data.transcription) updates.transcription = data.transcription;
        if (data.segments) updates.segments = data.segments;
      } else if (type === 'error') {
        updates.status = 'failed';
        updates.error_message = data.error;
      }

      return updates;
    });
  }, [latestEvent]);

  // Fetch full job data when completed
  useEffect(() => {
    if (isDone && currentJob?.id) {
      api.getJob(currentJob.id).then(setCurrentJob).catch(console.error);
    }
  }, [isDone]);

  // ── Fetch Video Info ──
  // Creates a download-only job: the response carries metadata (title, duration,
  // thumbnail) AND the job begins downloading so the player + download buttons
  // light up before the user commits to transcription.
  const handleFetchInfo = async () => {
    if (!url.trim()) return;
    setError(null);
    setFetchingInfo(true);
    resetSSE();
    try {
      const downloadJob = await api.createDownloadJob(url.trim());
      setCurrentJob(downloadJob);
    } catch (e) {
      setError(e.message);
    } finally {
      setFetchingInfo(false);
    }
  };

  // ── Start Transcription ──
  const handleTranscribe = async () => {
    if (!url.trim()) return;
    setError(null);
    setLoading(true);
    resetSSE();

    try {
      const jobData = {
        url: url.trim(),
        asr_provider: asrProvider,
        language,
        start_time: startTime,
        end_time: endTime,
        split_duration: splitDuration ? parseInt(splitDuration) : null,
        context: context.trim() || null,
        llm_cleanup: llmCleanup,
        preview_job_id:
          currentJob?.video_path && currentJob.url === url.trim() ? currentJob.id : null,
      };

      const job = await api.createJob(jobData);
      setCurrentJob(job);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Seek video ──
  const handleSeekTo = (time) => {
    videoRef.current?.seekTo(time);
  };

  // ── Derived state ──
  const isProcessing = currentJob && !['completed', 'failed'].includes(currentJob.status);
  const videoSrc = currentJob?.video_path ? api.getVideoUrl(currentJob.id) : null;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div>
          <h1>Video Transcriber</h1>
          <div className="subtitle">Transcribe YouTube, Instagram & Facebook videos with AI</div>
        </div>
      </header>

      {/* Input Section */}
      <section className="input-section">
        <div className="url-input-row">
          <input
            type="text"
            className="url-input"
            placeholder="Paste YouTube, Instagram, or Facebook video URL..."
            value={url}
            onChange={(e) => {
              const next = e.target.value;
              setUrl(next);
              // Drop any stale job tied to a different URL so we don't reuse the wrong video.
              if (currentJob && currentJob.url !== next.trim()) {
                setCurrentJob(null);
              }
            }}
            onKeyDown={(e) => e.key === 'Enter' && handleFetchInfo()}
          />
          <button className="btn btn-secondary" onClick={handleFetchInfo} disabled={fetchingInfo || !url.trim()}>
            {fetchingInfo ? <span className="spinner" /> : 'Fetch Info'}
          </button>
          <button className="btn btn-primary" onClick={handleTranscribe} disabled={loading || isProcessing || !url.trim()}>
            {loading ? <span className="spinner" /> : 'Transcribe'}
          </button>
        </div>

        {currentJob?.title && (
          <div style={{ marginBottom: 16, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>{currentJob.title}</strong>
            {currentJob.duration > 0 && ` \u2022 ${Math.floor(currentJob.duration / 60)}m ${Math.floor(currentJob.duration % 60)}s`}
          </div>
        )}

        <div className="options-row">
          <div className="option-group">
            <label>ASR Engine</label>
            <select value={asrProvider} onChange={(e) => setAsrProvider(e.target.value)}>
              <option value="openai">OpenAI Whisper API</option>
              <option value="docker">faster-whisper (Docker)</option>
            </select>
          </div>
          <div className="option-group">
            <label>Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="auto">Auto-detect</option>
              <option value="en">English</option>
              <option value="hi">Hindi</option>
              <option value="mr">Marathi</option>
              <option value="ta">Tamil</option>
              <option value="te">Telugu</option>
              <option value="bn">Bengali</option>
              <option value="gu">Gujarati</option>
              <option value="kn">Kannada</option>
              <option value="pa">Punjabi</option>
              <option value="ur">Urdu</option>
            </select>
          </div>
          <div className="option-group">
            <label>Split every (sec)</label>
            <input
              type="number"
              placeholder="e.g. 600"
              min="60"
              step="60"
              value={splitDuration}
              onChange={(e) => setSplitDuration(e.target.value)}
              style={{ width: 100 }}
            />
          </div>
        </div>

        {/* Context & Options */}
        <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <div className="option-group" style={{ flex: 1 }}>
            <label>Context (optional)</label>
            <input
              type="text"
              className="url-input"
              placeholder="e.g. Hindi news about Union Budget, Cricket commentary, Tech tutorial..."
              value={context}
              onChange={(e) => setContext(e.target.value)}
              style={{ fontSize: '0.9rem', padding: '8px 12px' }}
            />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap', paddingBottom: 4 }}>
            <input type="checkbox" checked={llmCleanup} onChange={(e) => setLlmCleanup(e.target.checked)} style={{ accentColor: 'var(--accent)' }} />
            LLM Cleanup
          </label>
        </div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      {/* Progress */}
      {isProcessing && (
        <ProgressPanel
          status={currentJob?.status}
          progress={currentJob?.progress || 0}
          message={currentJob?.progress_message}
        />
      )}
      {currentJob?.status === 'failed' && (
        <ProgressPanel
          status="failed"
          progress={currentJob.progress}
          message={currentJob.progress_message}
          error={currentJob.error_message}
        />
      )}

      {/* Main Content */}
      <div className="main-content">
        {/* Left: Video + Range Selector */}
        <div>
          <div className="card">
            <div className="card-header">
              <h2>Video</h2>
              {currentJob?.platform && (
                <span className={`platform-badge ${currentJob.platform}`}>
                  {currentJob.platform}
                </span>
              )}
              <DownloadButtons
                jobId={currentJob?.id}
                title={currentJob?.title}
                videoPath={currentJob?.video_path}
              />
            </div>
            <div className="card-body">
              <VideoPlayer
                ref={videoRef}
                src={videoSrc}
                thumbnail={currentJob?.thumbnail_url}
                onTimeUpdate={setVideoTime}
              />
              <RangeSelector
                duration={currentJob?.duration}
                startTime={startTime}
                endTime={endTime}
                onStartChange={setStartTime}
                onEndChange={setEndTime}
              />
            </div>
          </div>
        </div>

        {/* Right: Transcription */}
        <div className="card">
          <div className="card-header">
            <h2>Transcription</h2>
          </div>
          <div className="card-body">
            <TranscriptionPanel
              transcription={currentJob?.transcription}
              segments={currentJob?.segments}
              currentTime={videoTime}
              onSeekTo={handleSeekTo}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
