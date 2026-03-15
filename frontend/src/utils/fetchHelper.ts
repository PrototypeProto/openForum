const BASE_HEADERS = {
  "Content-Type": "application/json",
};

export async function postJSON<T>(
  url: string,
  body: unknown,
  token?: string,
): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      ...BASE_HEADERS,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) throw new Error(data.detail?.[0]?.msg ?? "request failed");

  return data as T;
}

export async function getJSON<T>(url: string, token?: string): Promise<T> {
  const res = await fetch(url, {
    method: "GET",
    headers: {
      ...BASE_HEADERS,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) throw new Error(data.detail?.[0]?.msg ?? "request failed");

  return data as T;
}
