import { deleteReq, getJSON, postFormData } from "../../utils/fetchHelper";
import { API } from "../endpoints/api";
import type { APIResponse } from "../../types/authType";
import type {
  TempFileRead,
  TempFileUploadResponse,
  StorageStatusRead,
} from "../../types/tempfsTypes";

export interface UploadOptions {
  file: File;
  downloadPermission: "public" | "self" | "password";
  password: string | null;
  lifetimeSeconds: number;
  compress: boolean;
}

export interface TempFilePublicInfo {
  file_id: string;
  original_filename: string;
  original_size: number;
  stored_size: number;
  is_compressed: boolean;
  download_permission: string;
  expires_at: string;
  requires_password: boolean;
}

export async function getFileInfo(
  fileId: string,
): Promise<APIResponse<TempFilePublicInfo>> {
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

  // postFormData injects X-CSRF-Token and omits Content-Type so the
  // browser can set the multipart boundary correctly.
  const res = await postFormData(API.tempfs.upload, form);

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

export async function getStorageStatus(): Promise<
  APIResponse<StorageStatusRead>
> {
  return getJSON<StorageStatusRead>(API.tempfs.storage);
}

export async function deleteFile(fileId: string): Promise<APIResponse<null>> {
  return deleteReq(API.tempfs.delete(fileId));
}

/**
 * Download a file. Password (if required) is sent as X-File-Password header,
 * never as a query parameter — query params leak into server logs and browser
 * history, defeating the purpose of password protection.
 */
export async function downloadFile(
  fileId: string,
  wantCompressed: boolean,
  password: string | null,
): Promise<string | null> {
  const url = API.tempfs.download(fileId, wantCompressed);

  const headers: Record<string, string> = {};
  if (password) headers["X-File-Password"] = password;

  const res = await fetch(url, {
    credentials: "include",
    headers,
  });

  if (!res.ok) {
    return res.status === 404 ? "File not found or expired" : "Download failed";
  }

  // Extract filename from Content-Disposition header per RFC 6266.
  // Prefer filename*=UTF-8''<percent-encoded> (set by the backend for
  // non-ASCII names) over the ASCII-only filename="..." fallback.
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  const asciiMatch = disposition.match(/filename="([^"]+)"/);
  const rawFilename = utf8Match
    ? decodeURIComponent(utf8Match[1])
    : asciiMatch
      ? asciiMatch[1]
      : "download";
  const filename = rawFilename || "download";

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
