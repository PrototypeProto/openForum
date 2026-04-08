import { deleteReq, getJSON } from "../../utils/fetchHelper";
import { API } from "../endpoints/api";
import type { APIResponse } from "../../types/authType";
import type {
  TempFileRead,
  TempFileUploadResponse,
  StorageStatusRead,
} from "../../types/tempfsTypes";

export interface UploadOptions {
  file: File
  downloadPermission: "public" | "self" | "password"
  password: string | null
  lifetimeSeconds: number
  compress: boolean
}

export interface TempFilePublicInfo {
  file_id: string
  original_filename: string
  original_size: number
  stored_size: number
  is_compressed: boolean
  download_permission: string
  expires_at: string
  requires_password: boolean
}

export async function getFileInfo(fileId: string): Promise<APIResponse<TempFilePublicInfo>> {
  return getJSON<TempFilePublicInfo>(API.tempfs.info(fileId));
}

export async function uploadFile(
  opts: UploadOptions,
): Promise<APIResponse<TempFileUploadResponse>> {
  const form = new FormData();
  form.append("file", opts.file);
  form.append("download_permission", opts.downloadPermission);
  form.append("lifetime_seconds", String(opts.lifetimeSeconds));
  form.append("compress", String(opts.compress));
  if (opts.password) form.append("password", opts.password);

  const res = await fetch(API.tempfs.upload, {
    method: "POST",
    credentials: "include",
    body: form,
    // No Content-Type header — browser sets multipart boundary automatically
  });

  const data = await res.json().catch(() => ({}));
  return {
    data: res.ok ? (data as TempFileUploadResponse) : null,
    ok: res.ok,
    statusCode: res.status,
    error: res.ok
      ? null
      : (data.detail?.[0]?.msg ?? data.detail ?? "Upload failed"),
  };
}

export async function listMyFiles(): Promise<APIResponse<TempFileRead[]>> {
  return getJSON<TempFileRead[]>(API.tempfs.files);
}

export async function getStorageStatus(): Promise<APIResponse<StorageStatusRead>> {
  return getJSON<StorageStatusRead>(API.tempfs.storage);
}

export async function deleteFile(fileId: string): Promise<APIResponse<null>> {
  return deleteReq(API.tempfs.delete(fileId));
}

/**
 * Initiates a file download by constructing the download URL with optional
 * query params and triggering a browser anchor click.
 * Returns an error string if the server responds with non-200.
 */
export async function downloadFile(
  fileId: string,
  wantCompressed: boolean,
  password: string | null,
): Promise<string | null> {
  const url = API.tempfs.download(fileId, wantCompressed, password ?? undefined);

  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    return res.status === 404 ? "File not found or expired" : "Download failed";
  }

  // Extract filename from Content-Disposition header if present
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : "download";

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objectUrl);

  return null; // null = success
}
