import React, { useRef, useEffect, useImperativeHandle, forwardRef, useState } from 'react';

const VideoPlayer = forwardRef(({ src, thumbnail, onTimeUpdate }, ref) => {
  const videoRef = useRef(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useImperativeHandle(ref, () => ({
    seekTo: (time) => {
      if (videoRef.current) {
        videoRef.current.currentTime = time;
      }
    },
    getCurrentTime: () => videoRef.current?.currentTime || 0,
    getDuration: () => videoRef.current?.duration || 0,
    play: () => videoRef.current?.play(),
    pause: () => videoRef.current?.pause(),
  }));

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      onTimeUpdate?.(video.currentTime);
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    return () => video.removeEventListener('timeupdate', handleTimeUpdate);
  }, [onTimeUpdate]);

  if (!src) {
    return (
      <div className="video-placeholder">
        {thumbnail ? (
          <img src={thumbnail} alt="thumbnail" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span>Paste a video URL above to get started</span>
        )}
      </div>
    );
  }

  return (
    <div className="video-container">
      <video
        ref={videoRef}
        src={src}
        controls
        preload="metadata"
        onLoadedData={() => setIsLoaded(true)}
        style={{ background: '#000' }}
      />
    </div>
  );
});

VideoPlayer.displayName = 'VideoPlayer';
export default VideoPlayer;
