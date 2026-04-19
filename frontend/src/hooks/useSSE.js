import { useEffect, useRef, useCallback, useState } from 'react';
import { api } from './useApi';

/**
 * Hook to subscribe to SSE events for a transcription job.
 */
export function useSSE(jobId) {
  const [latestEvent, setLatestEvent] = useState(null);
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

    source.onerror = () => source.close();

    const eventTypes = [
      'downloading', 'extracting_audio', 'transcribing',
      'completed', 'error', 'progress'
    ];

    eventTypes.forEach(type => {
      source.addEventListener(type, (e) => {
        const data = JSON.parse(e.data);
        setLatestEvent({ type, data, timestamp: Date.now() });

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
    setLatestEvent(null);
    setIsDone(false);
  }, []);

  return { latestEvent, isDone, reset };
}
