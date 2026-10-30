import { getApiBaseUrl } from "@/lib/api/config";
import { authClient } from "@/lib/auth/client";
import {
  parseAskResponse,
  validateAskQuestionInput,
  type AskResult,
} from "@/lib/ask/parse-ask-response";
import { formatDocumentStatus } from "@/lib/documents/format-document-status";
import {
  parseSearchResponse,
  type SearchResult,
  validateSearchQueryInput,
  validateSearchTopK,
} from "@/lib/search/parse-search-response";

export { formatDocumentStatus };
export type { SearchMatch, SearchResult, SearchTopK } from "@/lib/search/parse-search-response";
export { SEARCH_TOP_K_OPTIONS } from "@/lib/search/parse-search-response";
export type { AskResult, AskSource } from "@/lib/ask/parse-ask-response";
export { validateAskQuestionInput } from "@/lib/ask/parse-ask-response";

export type CollectionRecord = {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
};

export type DocumentRecord = {
  id: string;
  collection_id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  content_hash_sha256: string | null;
  created_at: string;
  updated_at: string;
};

export const MAX_DOCUMENT_UPLOAD_BYTES = 10 * 1024 * 1024;

const DOCUMENT_ALLOWED_EXTENSIONS = new Set([".pdf", ".txt", ".md"]);

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
  if (status === 400) {
    return "The upload was rejected (400). Check file type and content.";
  }
  if (status === 404) {
    return "Collection not found (404). It may have been removed or you lack access.";
  }
  if (status === 409) {
    return "This document cannot be processed right now (409). It may already be processing or ready for indexing.";
  }
  if (status === 413) {
    return "File exceeds the maximum upload size (413). Limit is 10 MB.";
  }
  if (status === 422) {
    return "The request could not be processed (422). Check input or document content.";
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
    if (body && typeof body === "object") {
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
  const isFormDataBody =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !headers.has("Content-Type") && !isFormDataBody) {
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

function fileExtensionLower(name: string): string {
  const lastDot = name.lastIndexOf(".");
  if (lastDot <= 0) {
    return "";
  }
  return name.slice(lastDot).toLowerCase();
}

/** Returns an error message, or null when the file passes client-side checks. */
export function validateDocumentFile(file: File): string | null {
  if (file.size === 0) {
    return "Choose a non-empty file.";
  }
  if (file.size > MAX_DOCUMENT_UPLOAD_BYTES) {
    return "File must be 10 MB or smaller.";
  }
  const extension = fileExtensionLower(file.name);
  if (!DOCUMENT_ALLOWED_EXTENSIONS.has(extension)) {
    return "Only PDF, TXT, and MD files are allowed.";
  }
  return null;
}

const DOCUMENT_PROCESS_STATUSES = new Set([
  "UPLOADED",
  "PROCESSING",
  "PROCESSED",
  "READY",
  "FAILED",
]);

export type DocumentProcessResult = {
  id: string;
  status: string;
  chunk_count: number;
};

export async function processDocument(
  collectionId: string,
  documentId: string,
): Promise<
  | { ok: true; process: DocumentProcessResult }
  | { ok: false; error: ApiClientError }
> {
  const result = await authedApiRequest(
    `/collections/${encodeURIComponent(collectionId)}/documents/${encodeURIComponent(documentId)}/process`,
    { method: "POST" },
  );
  if (!result.ok) {
    return result;
  }

  let payload: unknown;
  try {
    payload = await result.response.json();
  } catch {
    return {
      ok: false,
      error: { message: "The API returned invalid JSON after processing." },
    };
  }

  if (
    !payload ||
    typeof payload !== "object" ||
    typeof (payload as DocumentProcessResult).id !== "string" ||
    typeof (payload as DocumentProcessResult).status !== "string" ||
    typeof (payload as DocumentProcessResult).chunk_count !== "number" ||
    !Number.isFinite((payload as DocumentProcessResult).chunk_count) ||
    (payload as DocumentProcessResult).chunk_count < 0 ||
    !DOCUMENT_PROCESS_STATUSES.has((payload as DocumentProcessResult).status)
  ) {
    return {
      ok: false,
      error: { message: "The API returned an unexpected process response." },
    };
  }

  return { ok: true, process: payload as DocumentProcessResult };
}

export type DocumentIndexResult = {
  id: string;
  status: string;
  embedding_model: string;
  embedded_chunk_count: number;
};

export async function indexDocument(
  collectionId: string,
  documentId: string,
): Promise<
  | { ok: true; index: DocumentIndexResult }
  | { ok: false; error: ApiClientError }
> {
  const result = await authedApiRequest(
    `/collections/${encodeURIComponent(collectionId)}/documents/${encodeURIComponent(documentId)}/index`,
    { method: "POST" },
  );
  if (!result.ok) {
    return result;
  }

  let payload: unknown;
  try {
    payload = await result.response.json();
  } catch {
    return {
      ok: false,
      error: { message: "The API returned invalid JSON after indexing." },
    };
  }

  if (
    !payload ||
    typeof payload !== "object" ||
    typeof (payload as DocumentIndexResult).id !== "string" ||
    (payload as DocumentIndexResult).status !== "READY" ||
    typeof (payload as DocumentIndexResult).embedding_model !== "string" ||
    !(payload as DocumentIndexResult).embedding_model.trim() ||
    typeof (payload as DocumentIndexResult).embedded_chunk_count !== "number" ||
    !Number.isInteger((payload as DocumentIndexResult).embedded_chunk_count) ||
    (payload as DocumentIndexResult).embedded_chunk_count <= 0
  ) {
    return {
      ok: false,
      error: { message: "The API returned an unexpected index response." },
    };
  }

  return { ok: true, index: payload as DocumentIndexResult };
}

export async function deleteDocument(
  collectionId: string,
  documentId: string,
): Promise<{ ok: true } | { ok: false; error: ApiClientError }> {
  const result = await authedApiRequest(
    `/collections/${encodeURIComponent(collectionId)}/documents/${encodeURIComponent(documentId)}`,
    { method: "DELETE" },
  );
  if (!result.ok) {
    return result;
  }

  if (result.response.status !== 204) {
    return {
      ok: false,
      error: {
        message: `Unexpected API response after delete (${result.response.status}).`,
      },
    };
  }

  return { ok: true };
}

export async function searchCollection(
  collectionId: string,
  query: string,
  topK: number = 5,
): Promise<
  | { ok: true; search: SearchResult }
  | { ok: false; error: ApiClientError }
> {
  const queryError = validateSearchQueryInput(query);
  if (queryError) {
    return { ok: false, error: { message: queryError, status: 422 } };
  }
  if (!validateSearchTopK(topK)) {
    return {
      ok: false,
      error: { message: "top_k must be 3, 5, or 10.", status: 422 },
    };
  }

  const trimmedQuery = query.trim();
  const result = await authedApiRequest(
    `/collections/${encodeURIComponent(collectionId)}/search`,
    {
      method: "POST",
      body: JSON.stringify({ query: trimmedQuery, top_k: topK }),
    },
  );
  if (!result.ok) {
    return result;
  }

  let payload: unknown;
  try {
    payload = await result.response.json();
  } catch {
    return {
      ok: false,
      error: { message: "The API returned invalid JSON after search." },
    };
  }

  const parsed = parseSearchResponse(payload);
  if (!parsed.ok) {
    return { ok: false, error: { message: parsed.error } };
  }

  return { ok: true, search: parsed.result };
}

export async function askCollection(
  collectionId: string,
  question: string,
  topK: number = 5,
): Promise<
  | { ok: true; ask: AskResult }
  | { ok: false; error: ApiClientError }
> {
  const questionError = validateAskQuestionInput(question);
  if (questionError) {
    return { ok: false, error: { message: questionError, status: 422 } };
  }
  if (!validateSearchTopK(topK)) {
    return {
      ok: false,
      error: { message: "top_k must be 3, 5, or 10.", status: 422 },
    };
  }

  const trimmedQuestion = question.trim();
  const result = await authedApiRequest(
    `/collections/${encodeURIComponent(collectionId)}/ask`,
    {
      method: "POST",
      body: JSON.stringify({ question: trimmedQuestion, top_k: topK }),
    },
  );
  if (!result.ok) {
    return result;
  }

  let payload: unknown;
  try {
    payload = await result.response.json();
  } catch {
    return {
      ok: false,
      error: { message: "The API returned invalid JSON after ask." },
    };
  }

  const parsed = parseAskResponse(payload);
  if (!parsed.ok) {
    return { ok: false, error: { message: parsed.error } };
  }

  return { ok: true, ask: parsed.result };
}

export async function fetchDocuments(
  collectionId: string,
): Promise<
  | { ok: true; documents: DocumentRecord[] }
  | { ok: false; error: ApiClientError }
> {
  const result = await authedApiRequest(
    `/collections/${encodeURIComponent(collectionId)}/documents`,
    { method: "GET" },
  );
  if (!result.ok) {
    return result;
  }

  let payload: unknown;
  try {
    payload = await result.response.json();
  } catch {
    return {
      ok: false,
      error: { message: "The API returned invalid JSON for documents." },
    };
  }

  if (!Array.isArray(payload)) {
    return {
      ok: false,
      error: { message: "The API returned an unexpected documents payload." },
    };
  }

  const documents: DocumentRecord[] = [];
  for (const item of payload) {
    if (
      item &&
      typeof item === "object" &&
      typeof (item as DocumentRecord).id === "string" &&
      typeof (item as DocumentRecord).original_filename === "string" &&
      typeof (item as DocumentRecord).size_bytes === "number" &&
      typeof (item as DocumentRecord).status === "string" &&
      typeof (item as DocumentRecord).created_at === "string"
    ) {
      documents.push(item as DocumentRecord);
    }
  }

  return { ok: true, documents };
}

export async function uploadDocument(
  collectionId: string,
  file: File,
): Promise<
  | { ok: true; document: DocumentRecord }
  | { ok: false; error: ApiClientError }
> {
  const formData = new FormData();
  formData.append("file", file);

  const result = await authedApiRequest(
    `/collections/${encodeURIComponent(collectionId)}/documents`,
    {
      method: "POST",
      body: formData,
    },
  );
  if (!result.ok) {
    return result;
  }

  let payload: unknown;
  try {
    payload = await result.response.json();
  } catch {
    return {
      ok: false,
      error: { message: "The API returned invalid JSON after upload." },
    };
  }

  if (
    !payload ||
    typeof payload !== "object" ||
    typeof (payload as DocumentRecord).id !== "string" ||
    typeof (payload as DocumentRecord).original_filename !== "string"
  ) {
    return {
      ok: false,
      error: { message: "The API returned an unexpected upload response." },
    };
  }

  return { ok: true, document: payload as DocumentRecord };
}
