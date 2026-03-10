import { useEffect, useRef, useCallback, useState } from 'react';
import { api } from './useApi';

/**
 * Hook to subscribe to SSE events for a transcription job.
 */
export function useSSE(jobId) {
  const [events, setEvents] = useState([]);
  const [latestEvent, setLatestEvent] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const sourceRef = useRef(null);

  const connect = useCallback(() => {
    if (!jobId) return;
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    const url = api.getSSEUrl(jobId);
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setIsConnected(true);
    source.onerror = () => {
      setIsConnected(false);
      source.close();
    };

    // Listen to all event types
    const eventTypes = [
      'downloading', 'extracting_audio', 'transcribing',
      'generating_mindmap', 'completed', 'error', 'progress'
    ];

    eventTypes.forEach(type => {
      source.addEventListener(type, (e) => {
        const data = JSON.parse(e.data);
        const event = { type, data, timestamp: Date.now() };
        setEvents(prev => [...prev, event]);
        setLatestEvent(event);

        if (type === 'completed' || type === 'error') {
          setIsDone(true);
          source.close();
        }
      });
    });
  }, [jobId]);

  useEffect(() => {
    connect();
    return () => {
      if (sourceRef.current) {
        sourceRef.current.close();
      }
    };
  }, [connect]);

  const reset = useCallback(() => {
    setEvents([]);
    setLatestEvent(null);
    setIsDone(false);
    setIsConnected(false);
  }, []);

  return { events, latestEvent, isConnected, isDone, reset };
}
