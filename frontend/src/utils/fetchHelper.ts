import type { APIResponse } from "../types/authType";

const BASE_HEADERS = {
  "Content-Type": "application/json",
};

const BASE_OPTIONS = {
  credentials: "include" as RequestCredentials,
  headers: BASE_HEADERS,
};

// Lazily imported to avoid a circular dependency:
// fetchHelper ← authService ← AuthContext ← fetchHelper
let _handleUnauthorized: (() => Promise<void>) | null = null;

export function registerUnauthorizedHandler(handler: () => Promise<void>) {
  _handleUnauthorized = handler;
}

async function handleResponse<T>(res: Response): Promise<APIResponse<T>> {
  const data = await res.json().catch(() => ({}));

  if (res.status === 401 && _handleUnauthorized) {
    // Session invalidated (role change, reuse detected, expired).
    // Delegate to AuthContext which will attempt rotation then re-login.
    await _handleUnauthorized();
  }

  return {
    data: res.ok ? (data as T) : null,
    ok: res.ok,
    statusCode: res.status,
    error: res.ok
      ? null
      : (data.detail?.[0]?.msg ??
        data.detail ??
        "Failed to retrieve error message"),
  };
}

export async function postJSON<T>(
  url: string,
  body: unknown,
): Promise<APIResponse<T>> {
  const res = await fetch(url, {
    method: "POST",
    ...BASE_OPTIONS,
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function patchJSON<T>(
  url: string,
  body: unknown,
): Promise<APIResponse<T>> {
  const res = await fetch(url, {
    method: "PATCH",
    ...BASE_OPTIONS,
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function deleteReq(url: string): Promise<APIResponse<null>> {
  const res = await fetch(url, {
    method: "DELETE",
    ...BASE_OPTIONS,
  });
  return handleResponse<null>(res);
}

export async function getJSON<T>(
  url: string,
  params?: Record<string, unknown>,
): Promise<APIResponse<T>> {
  const urlWithParams = params
    ? `${url}?${new URLSearchParams(params as Record<string, string>).toString()}`
    : url;

  const res = await fetch(urlWithParams, {
    method: "GET",
    ...BASE_OPTIONS,
  });
  return handleResponse<T>(res);
}

export async function getRaw(url: string): Promise<Response> {
  return fetch(url, {
    method: "GET",
    ...BASE_OPTIONS,
  });
}
