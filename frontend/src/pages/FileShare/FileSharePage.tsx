import { useState, useRef } from "react";
import { Navbar } from "../../components/Navbar";
import { useTempFS } from "../../hooks/useTempFS";
import type { TempFileRead } from "../../types/tempfsTypes";
import "./FileSharePage.css";

// ── helpers ──────────────────────────────────────────────────────────────────

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
  if (diff < 3600)  return `${Math.floor(diff / 60)}m remaining`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h remaining`;
  return `${Math.floor(diff / 86400)}d remaining`;
}

// ── Upload form ───────────────────────────────────────────────────────────────

const LIFETIME_OPTIONS = [
  { label: "1 hour",  value: 3600 },
  { label: "6 hours", value: 21600 },
  { label: "1 day",   value: 86400 },
  { label: "3 days",  value: 259200 },
  { label: "1 week",  value: 604800 },
];

interface UploadFormProps {
  onUpload: (opts: {
    file: File;
    downloadPermission: "public" | "self" | "password";
    password: string | null;
    lifetimeSeconds: number;
    compress: boolean;
  }) => void;
  uploading: boolean;
  error: string | null;
}

function UploadForm({ onUpload, uploading, error }: UploadFormProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [permission, setPermission] = useState<"public" | "self" | "password">("public");
  const [password, setPassword] = useState("");
  const [lifetime, setLifetime] = useState(3600);
  const [compress, setCompress] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  function handleSubmit() {
    if (!selectedFile) return;
    onUpload({
      file: selectedFile,
      downloadPermission: permission,
      password: permission === "password" ? password || null : null,
      lifetimeSeconds: lifetime,
      compress,
    });
  }

  return (
    <div className="tfs-card">
      <h2 className="tfs-card-title">Upload File</h2>

      <div className="tfs-field">
        <label className="tfs-label">File</label>
        <input
          ref={fileRef}
          type="file"
          className="tfs-file-input"
          onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
        />
        {selectedFile && (
          <span className="tfs-file-meta">
            {selectedFile.name} — {formatBytes(selectedFile.size)}
          </span>
        )}
      </div>

      <div className="tfs-field">
        <label className="tfs-label">Lifetime</label>
        <select
          className="tfs-select"
          value={lifetime}
          onChange={(e) => setLifetime(Number(e.target.value))}
        >
          {LIFETIME_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      <div className="tfs-field">
        <label className="tfs-label">Download access</label>
        <div className="tfs-radio-group">
          {(["public", "self", "password"] as const).map((p) => (
            <label key={p} className="tfs-radio-label">
              <input
                type="radio"
                name="permission"
                value={p}
                checked={permission === p}
                onChange={() => setPermission(p)}
              />
              {p === "public" ? "Public link" : p === "self" ? "Only me" : "Password-protected"}
            </label>
          ))}
        </div>
      </div>

      {permission === "password" && (
        <div className="tfs-field">
          <label className="tfs-label">Password</label>
          <input
            type="password"
            className="tfs-input"
            placeholder="Set a download password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
      )}

      <div className="tfs-field tfs-field--inline">
        <label className="tfs-label">Compress (zstd)</label>
        <input
          type="checkbox"
          checked={compress}
          onChange={(e) => setCompress(e.target.checked)}
          className="tfs-checkbox"
        />
        <span className="tfs-hint">Stored compressed if smaller</span>
      </div>

      {error && <p className="tfs-error">{error}</p>}

      <button
        className="tfs-btn tfs-btn--primary"
        onClick={handleSubmit}
        disabled={!selectedFile || uploading}
      >
        {uploading ? "Uploading…" : "Upload"}
      </button>
    </div>
  );
}

// ── File row ──────────────────────────────────────────────────────────────────

function FileRow({ file, onDelete }: { file: TempFileRead; onDelete: (id: string) => void }) {
  const downloadUrl = `${window.location.origin}/file-share/download/${file.file_id}`;
  return (
    <div className="tfs-file-row">
      <div className="tfs-file-row__main">
        <span className="tfs-file-row__name">{file.original_filename}</span>
        <span className="tfs-file-row__meta">
          {formatBytes(file.original_size)}
          {file.is_compressed && (
            <span className="tfs-badge">zstd → {formatBytes(file.stored_size)}</span>
          )}
        </span>
      </div>
      <div className="tfs-file-row__right">
        <span className="tfs-file-row__perm">{file.download_permission}</span>
        <span className="tfs-file-row__expiry">{formatExpiry(file.expires_at)}</span>
        <button
          className="tfs-icon-btn"
          title="Copy download link"
          onClick={() => navigator.clipboard.writeText(downloadUrl)}
        >📋</button>
        <button
          className="tfs-icon-btn tfs-icon-btn--danger"
          title="Delete"
          onClick={() => onDelete(file.file_id)}
        >🗑</button>
      </div>
    </div>
  );
}

// ── Storage meter ─────────────────────────────────────────────────────────────

function StorageMeter({ used, quota }: { used: number; quota: number }) {
  const pct = Math.min(100, (used / quota) * 100);
  const color = pct > 90 ? "#dc2626" : pct > 70 ? "#f59e0b" : "#6366f1";
  return (
    <div className="tfs-storage">
      <div className="tfs-storage__labels">
        <span>Storage</span>
        <span>{formatBytes(used)} / {formatBytes(quota)}</span>
      </div>
      <div className="tfs-storage__bar">
        <div className="tfs-storage__fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function FileSharePage() {
  const {
    files, storage, loading, error,
    uploading, uploadError, lastUpload,
    upload, remove, removeError,
  } = useTempFS();

  return (
    <>
      <Navbar />
      <div className="tfs-page">
        <h1 className="tfs-heading">Temporary File Storage</h1>

        {storage && <StorageMeter used={storage.used_bytes} quota={storage.storage_cap_bytes} />}

        {lastUpload && (
          <div className="tfs-success">
            <strong>{lastUpload.original_filename}</strong> uploaded.{" "}
            <a href={`/file-share/download/${lastUpload.file_id}`} target="_blank" rel="noreferrer" className="tfs-link">
              Copy link
            </a>
            <span className="tfs-success__meta">
              {formatBytes(lastUpload.stored_size)} stored
              {lastUpload.is_compressed && ` (compressed from ${formatBytes(lastUpload.original_size)})`}
            </span>
          </div>
        )}

        <UploadForm onUpload={upload} uploading={uploading} error={uploadError} />

        <div className="tfs-card">
          <h2 className="tfs-card-title">Your Active Files</h2>
          {error && <p className="tfs-error">{error}</p>}
          {removeError && <p className="tfs-error">{removeError}</p>}
          {loading ? (
            <p className="tfs-muted">Loading…</p>
          ) : files.length === 0 ? (
            <p className="tfs-muted">No active files.</p>
          ) : (
            <div className="tfs-file-list">
              {files.map((f) => <FileRow key={f.file_id} file={f} onDelete={remove} />)}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
