import { useState, useEffect, useCallback } from "react";
import {
  listMyFiles,
  getStorageStatus,
  uploadFile,
  deleteFile,
  type UploadOptions,
} from "../services/tempfs/tempfsService";
import type { TempFileRead, StorageStatusRead, TempFileUploadResponse } from "../types/tempfsTypes";

interface UseTempFSResult {
  files: TempFileRead[]
  storage: StorageStatusRead | null
  loading: boolean
  error: string | null
  // upload form state
  uploading: boolean
  uploadError: string | null
  lastUpload: TempFileUploadResponse | null
  upload: (opts: UploadOptions) => Promise<void>
  // delete
  remove: (fileId: string) => Promise<void>
  removeError: string | null
}

export function useTempFS(): UseTempFSResult {
  const [files, setFiles] = useState<TempFileRead[]>([]);
  const [storage, setStorage] = useState<StorageStatusRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastUpload, setLastUpload] = useState<TempFileUploadResponse | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [filesRes, storageRes] = await Promise.all([
        listMyFiles(),
        getStorageStatus(),
      ]);
      if (filesRes.ok && filesRes.data) setFiles(filesRes.data);
      else setError(filesRes.error ?? "Failed to load files");
      if (storageRes.ok && storageRes.data) setStorage(storageRes.data);
      setLoading(false);
    }
    load();
  }, []);

  const upload = useCallback(async (opts: UploadOptions) => {
    setUploading(true);
    setUploadError(null);
    setLastUpload(null);

    const res = await uploadFile(opts);
    if (!res.ok || !res.data) {
      setUploadError(res.error ?? "Upload failed");
      setUploading(false);
      return;
    }

    setLastUpload(res.data);

    // Refresh file list and storage after upload
    const [filesRes, storageRes] = await Promise.all([
      listMyFiles(),
      getStorageStatus(),
    ]);
    if (filesRes.ok && filesRes.data) setFiles(filesRes.data);
    if (storageRes.ok && storageRes.data) setStorage(storageRes.data);

    setUploading(false);
  }, []);

  const remove = useCallback(async (fileId: string) => {
    setRemoveError(null);
    const res = await deleteFile(fileId);
    if (!res.ok) {
      setRemoveError(res.error ?? "Delete failed");
      return;
    }
    setFiles((prev) => prev.filter((f) => f.file_id !== fileId));
    // Refresh storage quota
    const storageRes = await getStorageStatus();
    if (storageRes.ok && storageRes.data) setStorage(storageRes.data);
  }, []);

  return {
    files,
    storage,
    loading,
    error,
    uploading,
    uploadError,
    lastUpload,
    upload,
    remove,
    removeError,
  };
}
