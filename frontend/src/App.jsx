import React, { useState, useRef, useCallback, useEffect } from 'react';
import VideoPlayer from './components/VideoPlayer';
import ProgressPanel from './components/ProgressPanel';
import TranscriptionPanel from './components/TranscriptionPanel';
import MindMap from './components/MindMap';
import RangeSelector from './components/RangeSelector';
import JobHistory from './components/JobHistory';
import { api } from './hooks/useApi';
import { useSSE } from './hooks/useSSE';

export default function App() {
  // ── State ──
  const [url, setUrl] = useState('');
  const [videoInfo, setVideoInfo] = useState(null);
  const [asrProvider, setAsrProvider] = useState('openai');
  const [language, setLanguage] = useState('hi');
  const [startTime, setStartTime] = useState(null);
  const [endTime, setEndTime] = useState(null);
  const [splitDuration, setSplitDuration] = useState('');
  const [prompt, setPrompt] = useState('');
  const [contextHint, setContextHint] = useState('');

  const [currentJob, setCurrentJob] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetchingInfo, setFetchingInfo] = useState(false);
  const [error, setError] = useState(null);

  const [activeTab, setActiveTab] = useState('transcription'); // transcription | mindmap
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
      else if (type === 'generating_mindmap') updates.status = 'generating_mindmap';
      else if (type === 'completed') {
        updates.status = 'completed';
        updates.progress = 100;
        if (data.transcription) updates.transcription = data.transcription;
        if (data.segments) updates.segments = data.segments;
        if (data.mindmap) updates.mindmap_mermaid = data.mindmap;
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
      loadJobs();
    }
  }, [isDone]);

  // ── Load jobs on mount ──
  const loadJobs = useCallback(async () => {
    try {
      const data = await api.listJobs();
      setJobs(data);
    } catch (e) {
      console.error('Failed to load jobs:', e);
    }
  }, []);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  // ── Fetch Video Info ──
  const handleFetchInfo = async () => {
    if (!url.trim()) return;
    setError(null);
    setFetchingInfo(true);
    try {
      const info = await api.fetchVideoInfo(url);
      setVideoInfo(info);
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
        prompt: prompt.trim() || null,
        context_hint: contextHint.trim() || null,
      };

      const job = await api.createJob(jobData);
      setCurrentJob(job);
      loadJobs();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Select from history ──
  const handleSelectJob = async (job) => {
    setError(null);
    try {
      const fullJob = await api.getJob(job.id);
      setCurrentJob(fullJob);
      setUrl(fullJob.url);
      if (fullJob.title) setVideoInfo({ title: fullJob.title, duration: fullJob.duration, thumbnail: fullJob.thumbnail_url });
    } catch (e) {
      setError(e.message);
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
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleFetchInfo()}
          />
          <button className="btn btn-secondary" onClick={handleFetchInfo} disabled={fetchingInfo || !url.trim()}>
            {fetchingInfo ? <span className="spinner" /> : 'Fetch Info'}
          </button>
          <button className="btn btn-primary" onClick={handleTranscribe} disabled={loading || isProcessing || !url.trim()}>
            {loading ? <span className="spinner" /> : 'Transcribe'}
          </button>
        </div>

        {videoInfo && (
          <div style={{ marginBottom: 16, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>{videoInfo.title}</strong>
            {videoInfo.duration > 0 && ` \u2022 ${Math.floor(videoInfo.duration / 60)}m ${Math.floor(videoInfo.duration % 60)}s`}
            {videoInfo.uploader && ` \u2022 ${videoInfo.uploader}`}
          </div>
        )}

        <div className="options-row">
          <div className="option-group">
            <label>ASR Engine</label>
            <select value={asrProvider} onChange={(e) => setAsrProvider(e.target.value)}>
              <option value="openai">OpenAI Whisper API</option>
              <option value="docker">faster-whisper (Docker)</option>
              <option value="huggingface">HuggingFace API</option>
            </select>
          </div>
          <div className="option-group">
            <label>Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="hi">Hindi</option>
              <option value="en">English</option>
              <option value="auto">Auto-detect</option>
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

        {/* Prompt & Context */}
        <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
          <div className="option-group" style={{ flex: 1 }}>
            <label>Whisper Prompt (optional)</label>
            <input
              type="text"
              className="url-input"
              placeholder="e.g. Hindi news discussion about Union Budget, GST, fiscal deficit..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              style={{ fontSize: '0.9rem', padding: '8px 12px' }}
            />
          </div>
          <div className="option-group" style={{ flex: 1 }}>
            <label>Topic Hint for LLM cleanup (optional)</label>
            <input
              type="text"
              className="url-input"
              placeholder="e.g. Cricket commentary, Bollywood movie review, Tech tutorial..."
              value={contextHint}
              onChange={(e) => setContextHint(e.target.value)}
              style={{ fontSize: '0.9rem', padding: '8px 12px' }}
            />
          </div>
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
            </div>
            <div className="card-body">
              <VideoPlayer
                ref={videoRef}
                src={videoSrc}
                thumbnail={videoInfo?.thumbnail || currentJob?.thumbnail_url}
                onTimeUpdate={setVideoTime}
              />
              <RangeSelector
                duration={videoInfo?.duration || currentJob?.duration}
                startTime={startTime}
                endTime={endTime}
                onStartChange={setStartTime}
                onEndChange={setEndTime}
              />
            </div>
          </div>

          <JobHistory jobs={jobs} onSelect={handleSelectJob} activeJobId={currentJob?.id} />
        </div>

        {/* Right: Transcription + Mind Map */}
        <div className="card">
          <div className="tabs">
            <button
              className={`tab ${activeTab === 'transcription' ? 'active' : ''}`}
              onClick={() => setActiveTab('transcription')}
            >
              Transcription
            </button>
            <button
              className={`tab ${activeTab === 'mindmap' ? 'active' : ''}`}
              onClick={() => setActiveTab('mindmap')}
            >
              Mind Map
            </button>
          </div>
          <div className="card-body">
            {activeTab === 'transcription' ? (
              <TranscriptionPanel
                transcription={currentJob?.transcription}
                segments={currentJob?.segments}
                currentTime={videoTime}
                onSeekTo={handleSeekTo}
              />
            ) : (
              <MindMap mermaidCode={currentJob?.mindmap_mermaid} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
