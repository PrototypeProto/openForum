import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Navbar } from "../../components/Navbar";
import { downloadFile, getFileInfo, type TempFilePublicInfo } from "../../services/tempfs/tempfsService";
import "./DownloadPage.css";

function formatBytes(b: number): string {
  if (b >= 1024 ** 3) return `${(b / 1024 ** 3).toFixed(2)} GB`;
  if (b >= 1024 ** 2) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  if (b >= 1024)      return `${(b / 1024).toFixed(0)} KB`;
  return `${b} B`;
}

function formatExpiry(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((d.getTime() - now.getTime()) / 1000);
  if (diff <= 0)    return "expired";
  if (diff < 3600)  return `expires in ${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `expires in ${Math.floor(diff / 3600)}h`;
  return `expires in ${Math.floor(diff / 86400)}d`;
}

export default function DownloadPage() {
  const { fileId } = useParams<{ fileId: string }>();

  const [info, setInfo]           = useState<TempFilePublicInfo | null>(null);
  const [infoLoading, setInfoLoading] = useState(true);
  const [notFound, setNotFound]   = useState(false);

  const [password, setPassword]           = useState("");
  const [wantCompressed, setWantCompressed] = useState(false);
  const [downloading, setDownloading]     = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [done, setDone]                   = useState(false);

  useEffect(() => {
    if (!fileId) return;
    async function load() {
      setInfoLoading(true);
      const res = await getFileInfo(fileId!);
      if (res.ok && res.data) {
        setInfo(res.data);
      } else {
        setNotFound(true);
      }
      setInfoLoading(false);
    }
    load();
  }, [fileId]);

  async function handleDownload() {
    if (!fileId) return;
    setDownloading(true);
    setDownloadError(null);

    const err = await downloadFile(fileId, wantCompressed, password || null);
    if (err) {
      setDownloadError(err);
    } else {
      setDone(true);
    }
    setDownloading(false);
  }

  return (
    <>
      <Navbar />
      <div className="dl-page">
        <div className="dl-card">

          {infoLoading ? (
            <p className="dl-muted">Loading…</p>
          ) : notFound ? (
            <>
              <div className="dl-card__icon">❌</div>
              <h1 className="dl-card__title">File not found</h1>
              <p className="dl-muted">This file may have expired or never existed.</p>
            </>
          ) : info ? (
            <>
              <div className="dl-card__icon">📦</div>
              <h1 className="dl-card__title">{info.original_filename}</h1>

              <div className="dl-meta">
                <div className="dl-meta__row">
                  <span className="dl-meta__label">Size</span>
                  <span className="dl-meta__value">
                    {formatBytes(info.original_size)}
                    {info.is_compressed && (
                      <span className="dl-badge">
                        stored {formatBytes(info.stored_size)} compressed
                      </span>
                    )}
                  </span>
                </div>
                <div className="dl-meta__row">
                  <span className="dl-meta__label">Expires</span>
                  <span className="dl-meta__value">{formatExpiry(info.expires_at)}</span>
                </div>
                <div className="dl-meta__row">
                  <span className="dl-meta__label">Access</span>
                  <span className="dl-meta__value">{info.download_permission}</span>
                </div>
              </div>

              {/* Password field — only shown if required */}
              {info.requires_password && (
                <div className="dl-field">
                  <label className="dl-label">Password</label>
                  <input
                    type="password"
                    className="dl-input"
                    placeholder="Enter download password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              )}

              {/* Compressed toggle — always available */}
              <label className="dl-toggle">
                <input
                  type="checkbox"
                  checked={wantCompressed}
                  onChange={(e) => setWantCompressed(e.target.checked)}
                />
                Download as compressed (.zst)
              </label>

              {downloadError && <p className="dl-error">{downloadError}</p>}
              {done && <p className="dl-success">Download started.</p>}

              <button
                className="dl-btn"
                onClick={handleDownload}
                disabled={downloading || (info.requires_password && !password)}
              >
                {downloading ? "Downloading…" : "Download"}
              </button>

              <p className="dl-note">
                This file is temporary and will be automatically deleted when it expires.
              </p>
            </>
          ) : null}

        </div>
      </div>
    </>
  );
}
