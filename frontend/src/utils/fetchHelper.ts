import type { APIResponse } from "../types/authType";
import { clearSession } from "../context/AuthContext";

const BASE_HEADERS = {
  "Content-Type": "application/json",
};

const BASE_OPTIONS = {
  credentials: "include" as RequestCredentials,
  headers: BASE_HEADERS,
};

/**
 * Read the csrf_token cookie set by the backend on login/refresh.
 * The cookie is intentionally non-HttpOnly so JS can read it here
 * and copy it into the X-CSRF-Token header on every mutating request.
 *
 * In production the backend uses the __Host- prefixed name; in dev/testing
 * it uses the plain name. We try the prefixed name first.
 */
function getCsrfToken(): string {
  const cookies = document.cookie.split(";").map((c) => c.trim());
  for (const name of ["__Host-csrf_token", "csrf_token"]) {
    const entry = cookies.find((c) => c.startsWith(`${name}=`));
    if (entry) return entry.slice(name.length + 1);
  }
  return "";
}

async function handleResponse<T>(res: Response): Promise<APIResponse<T>> {
  const data = await res.json().catch(() => ({}));

  if (res.status === 401) {
    // Session is genuinely over (revoked, reuse detected, role changed).
    // Token rotation is handled transparently by the server middleware so
    // a 401 here means re-authentication is required.
    // Wipe the cached user so the next mount starts clean.
    clearSession();
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
    headers: {
      ...BASE_HEADERS,
      "X-CSRF-Token": getCsrfToken(),
    },
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
    headers: {
      ...BASE_HEADERS,
      "X-CSRF-Token": getCsrfToken(),
    },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function deleteReq(url: string): Promise<APIResponse<null>> {
  const res = await fetch(url, {
    method: "DELETE",
    ...BASE_OPTIONS,
    headers: {
      ...BASE_HEADERS,
      "X-CSRF-Token": getCsrfToken(),
    },
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

/**
 * POST multipart/form-data with CSRF header.
 * Used for tempfs uploads where Content-Type must be set by the browser.
 */
export async function postFormData(
  url: string,
  body: FormData,
): Promise<Response> {
  return fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      "X-CSRF-Token": getCsrfToken(),
      // No Content-Type — browser sets multipart boundary automatically
    },
    body,
  });
}
