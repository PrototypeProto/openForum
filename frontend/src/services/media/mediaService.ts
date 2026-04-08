import { getJSON, getRaw } from "../../utils/fetchHelper";
import { API } from "../../services/endpoints/api";
import type { APIResponse } from "../../types/authType";
import type { MediaListResponse } from "../../types/mediaType";

export async function getMediaList(
  page: number,
): Promise<APIResponse<MediaListResponse>> {
  return getJSON<MediaListResponse>(API.media.list(page));
}

// Returns a blob URL you can pass directly to a <video> src
export async function getMediaFile(filename: string): Promise<string | null> {
  try {
    const res = await getRaw(API.media.getFile(filename));
    if (!res.ok) return null;
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}
