import type { APIResponse } from "../types/authType";

const BASE_HEADERS = {
  "Content-Type": "application/json",
};

const BASE_OPTIONS = {
  credentials: "include" as RequestCredentials,
  headers: BASE_HEADERS,
};

async function handleResponse<T>(res: Response): Promise<APIResponse<T>> {
  const data = await res.json().catch(() => ({}));

  if (res.status === 401) {
    // Session is genuinely over (revoked, reuse detected, user deleted).
    // Token rotation is handled transparently by the server middleware so
    // a 401 reaching the frontend means re-authentication is required.
    window.location.href = "/login";
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
