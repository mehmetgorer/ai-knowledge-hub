export type SearchMatch = {
  document_id: string;
  original_filename: string;
  chunk_index: number;
  text: string;
  source_kind: string;
  page_numbers: number[];
  cosine_distance: number;
};

export type SearchResult = {
  matches: SearchMatch[];
};

export const SEARCH_TOP_K_OPTIONS = [3, 5, 10] as const;

export type SearchTopK = (typeof SEARCH_TOP_K_OPTIONS)[number];

export function validateSearchQueryInput(raw: string): string | null {
  if (!raw.trim()) {
    return "Enter a non-empty search query.";
  }
  return null;
}

export function validateSearchTopK(value: number): value is SearchTopK {
  return (SEARCH_TOP_K_OPTIONS as readonly number[]).includes(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function parseMatch(item: unknown): SearchMatch | null {
  if (!item || typeof item !== "object") {
    return null;
  }
  const record = item as Record<string, unknown>;
  if (typeof record.document_id !== "string") {
    return null;
  }
  if (typeof record.original_filename !== "string") {
    return null;
  }
  if (
    typeof record.chunk_index !== "number" ||
    !Number.isInteger(record.chunk_index) ||
    record.chunk_index < 0
  ) {
    return null;
  }
  if (typeof record.text !== "string") {
    return null;
  }
  if (typeof record.source_kind !== "string") {
    return null;
  }
  if (!Array.isArray(record.page_numbers)) {
    return null;
  }
  const page_numbers: number[] = [];
  for (const page of record.page_numbers) {
    if (typeof page !== "number" || !Number.isInteger(page)) {
      return null;
    }
    page_numbers.push(page);
  }
  if (!isFiniteNumber(record.cosine_distance)) {
    return null;
  }
  return {
    document_id: record.document_id,
    original_filename: record.original_filename,
    chunk_index: record.chunk_index,
    text: record.text,
    source_kind: record.source_kind,
    page_numbers,
    cosine_distance: record.cosine_distance,
  };
}

export function parseSearchResponse(
  payload: unknown,
): { ok: true; result: SearchResult } | { ok: false; error: string } {
  if (!payload || typeof payload !== "object") {
    return { ok: false, error: "The API returned an unexpected search payload." };
  }
  const matchesRaw = (payload as { matches?: unknown }).matches;
  if (!Array.isArray(matchesRaw)) {
    return { ok: false, error: "The API returned an unexpected search payload." };
  }

  const matches: SearchMatch[] = [];
  for (const item of matchesRaw) {
    const parsed = parseMatch(item);
    if (!parsed) {
      return {
        ok: false,
        error: "The API returned an unexpected search match shape.",
      };
    }
    matches.push(parsed);
  }

  return { ok: true, result: { matches } };
}
