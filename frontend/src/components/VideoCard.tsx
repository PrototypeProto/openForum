import { useState, useEffect } from "react";
import "./VideoCard.css";
import { getMediaFile } from "../services/media/mediaService";

interface VideoCardProps {
  filename: string;
}

export default function VideoCard({ filename }: VideoCardProps) {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Revoke the blob URL on unmount to free memory
  useEffect(() => {
    return () => {
      if (videoUrl) URL.revokeObjectURL(videoUrl);
    };
  }, [videoUrl]);

  const handleLoad = async () => {
    if (videoUrl) return; // already loaded
    setLoading(true);
    const url = await getMediaFile(filename);
    setVideoUrl(url);
    setLoading(false);
  };

  return (
    <div className="video-card">
      {videoUrl ? (
        <video className="video-player" controls src={videoUrl} />
      ) : (
        <div className="video-placeholder" onClick={handleLoad}>
          <img src="/sasa.png" alt="placeholder" className="placeholder-img" />
          {loading ? (
            <span className="placeholder-label">Loading...</span>
          ) : (
            <span className="placeholder-label">Click to load</span>
          )}
        </div>
      )}
      <div className="video-card-footer">
        <span className="video-filename">File: {filename}</span>
      </div>
    </div>
  );
}
