export interface TempFileRead {
  file_id: string
  original_filename: string
  mime_type: string
  original_size: number
  stored_size: number
  is_compressed: boolean
  download_permission: "public" | "self" | "password"
  created_at: string
  expires_at: string
}

export interface TempFileUploadResponse {
  file_id: string
  original_filename: string
  original_size: number
  stored_size: number
  is_compressed: boolean
  expires_at: string
  download_permission: string
  used_bytes: number
  remaining_bytes: number
}

export interface StorageStatusRead {
  used_bytes: number
  remaining_bytes: number
  quota_bytes: number
}
