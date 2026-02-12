const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8001";

async function handleErrorResponse(res: Response, url: string) {
  const bodyText = await res.text();
  let parsed: any = null;
  try {
    parsed = bodyText ? JSON.parse(bodyText) : null;
  } catch (error) {
    parsed = null;
  }

  const requestId = parsed?.request_id;
  console.error("API request failed", {
    url,
    status: res.status,
    body: parsed ?? bodyText,
    request_id: requestId
  });

  const message =
    parsed?.message
    || parsed?.detail
    || bodyText
    || `Request failed with status ${res.status}`;
  throw new Error(message);
}

async function fetchJson(url: string, options?: RequestInit) {
  let res: Response;
  try {
    res = await fetch(url, options);
  } catch (error) {
    console.error("API request failed to reach server", { url, error });
    throw error;
  }

  if (!res.ok) {
    await handleErrorResponse(res, url);
  }
  return res.json();
}

export async function apiGet(path: string) {
  return fetchJson(`${API_BASE}${path}`);
}

export async function apiPost(path: string, body?: any) {
  return fetchJson(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined
  });
}

export async function apiPostFile(path: string, formData: FormData) {
  return fetchJson(`${API_BASE}${path}`, {
    method: "POST",
    body: formData
  });
}

export async function apiPut(path: string, body: any) {
  return fetchJson(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}
