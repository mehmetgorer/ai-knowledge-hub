import { getApiBaseUrl } from "@/lib/api/config";
import { authClient } from "@/lib/auth/client";

export type CollectionRecord = {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
};

export type ApiClientError = {
  message: string;
  status?: number;
};

async function obtainBearerToken(): Promise<
  { token: string } | { error: ApiClientError }
> {
  const { data, error } = await authClient.token();
  if (error) {
    return {
      error: {
        message:
          error.message || "Could not obtain a session token. Sign in again.",
      },
    };
  }

  const token = data?.token;
  if (!token) {
    return {
      error: {
        message: "No JWT available for this session. Sign in again.",
      },
    };
  }

  return { token };
}

function missingApiBaseError(): ApiClientError {
  return {
    message:
      "NEXT_PUBLIC_API_BASE_URL is not set. Add it to apps/web/.env.local (see .env.example).",
  };
}

function networkError(): ApiClientError {
  return {
    message:
      "Cannot reach the Python API. Start the API locally and check NEXT_PUBLIC_API_BASE_URL.",
  };
}

export function mapHttpStatusToMessage(status: number): string {
  if (status === 401) {
    return "Your session was rejected by the API (401). Sign in again or check API auth configuration.";
  }
  if (status === 422) {
    return "Invalid collection name (422). Use a non-empty name up to 255 characters.";
  }
  if (status === 503) {
    return "The API is unavailable (503). Check API auth configuration or database connectivity.";
  }
  return `Unexpected API response (${status}).`;
}

export async function readApiErrorMessage(response: Response): Promise<string> {
  const fallback = mapHttpStatusToMessage(response.status);
  try {
    const body: unknown = await response.json();
    if (response.status === 422 && body && typeof body === "object") {
      const detail = (body as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
      if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0];
        if (
          first &&
          typeof first === "object" &&
          "msg" in first &&
          typeof (first as { msg: unknown }).msg === "string"
        ) {
          return (first as { msg: string }).msg;
        }
      }
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export async function authedApiRequest(
  path: string,
  init: RequestInit = {},
): Promise<
  | { ok: true; response: Response }
  | { ok: false; error: ApiClientError }
> {
  const apiBase = getApiBaseUrl();
  if (!apiBase) {
    return { ok: false, error: missingApiBaseError() };
  }

  const tokenResult = await obtainBearerToken();
  if ("error" in tokenResult) {
    return { ok: false, error: tokenResult.error };
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${tokenResult.token}`);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    return { ok: false, error: networkError() };
  }

  if (!response.ok) {
    return {
      ok: false,
      error: {
        message: await readApiErrorMessage(response),
        status: response.status,
      },
    };
  }

  return { ok: true, response };
}

export async function fetchCollections(): Promise<
  | { ok: true; collections: CollectionRecord[] }
  | { ok: false; error: ApiClientError }
> {
  const result = await authedApiRequest("/collections", { method: "GET" });
  if (!result.ok) {
    return result;
  }

  let payload: unknown;
  try {
    payload = await result.response.json();
  } catch {
    return {
      ok: false,
      error: { message: "The API returned invalid JSON for collections." },
    };
  }

  if (!Array.isArray(payload)) {
    return {
      ok: false,
      error: { message: "The API returned an unexpected collections payload." },
    };
  }

  const collections: CollectionRecord[] = [];
  for (const item of payload) {
    if (
      item &&
      typeof item === "object" &&
      typeof (item as CollectionRecord).id === "string" &&
      typeof (item as CollectionRecord).name === "string" &&
      typeof (item as CollectionRecord).created_at === "string" &&
      typeof (item as CollectionRecord).updated_at === "string"
    ) {
      collections.push(item as CollectionRecord);
    }
  }

  return { ok: true, collections };
}

export async function createCollection(
  name: string,
): Promise<
  | { ok: true; collection: CollectionRecord }
  | { ok: false; error: ApiClientError }
> {
  const result = await authedApiRequest("/collections", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  if (!result.ok) {
    return result;
  }

  let payload: unknown;
  try {
    payload = await result.response.json();
  } catch {
    return {
      ok: false,
      error: { message: "The API returned invalid JSON after creating." },
    };
  }

  if (
    !payload ||
    typeof payload !== "object" ||
    typeof (payload as CollectionRecord).id !== "string" ||
    typeof (payload as CollectionRecord).name !== "string"
  ) {
    return {
      ok: false,
      error: { message: "The API returned an unexpected create response." },
    };
  }

  return { ok: true, collection: payload as CollectionRecord };
}

export function validateCollectionNameInput(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.length > 255) {
    return null;
  }
  return trimmed;
}
