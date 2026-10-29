export type AskSource = {
  source_id: string;
  document_id: string;
  original_filename: string;
  chunk_index: number;
  page_numbers: number[];
  text: string;
  cosine_distance: number;
};

export type AskResult = {
  answer: string;
  sources: AskSource[];
  model: string;
  grounded: boolean;
};

export function validateAskQuestionInput(raw: string): string | null {
  if (!raw.trim()) {
    return "Enter a non-empty question.";
  }
  return null;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function parseSourceId(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const normalized = value.trim();
  if (!/^S\d+$/.test(normalized)) {
    return null;
  }
  return normalized;
}

function parseAskSource(item: unknown): AskSource | null {
  if (!item || typeof item !== "object") {
    return null;
  }
  const record = item as Record<string, unknown>;
  const source_id = parseSourceId(record.source_id);
  if (!source_id) {
    return null;
  }
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
    source_id,
    document_id: record.document_id,
    original_filename: record.original_filename,
    chunk_index: record.chunk_index,
    page_numbers,
    text: record.text,
    cosine_distance: record.cosine_distance,
  };
}

export function parseAskResponse(
  payload: unknown,
): { ok: true; result: AskResult } | { ok: false; error: string } {
  if (!payload || typeof payload !== "object") {
    return { ok: false, error: "The API returned an unexpected ask payload." };
  }
  const record = payload as Record<string, unknown>;
  if (typeof record.answer !== "string") {
    return { ok: false, error: "The API returned an unexpected ask payload." };
  }
  if (typeof record.model !== "string" || !record.model.trim()) {
    return { ok: false, error: "The API returned an unexpected ask payload." };
  }
  if (typeof record.grounded !== "boolean") {
    return { ok: false, error: "The API returned an unexpected ask payload." };
  }
  if (!Array.isArray(record.sources)) {
    return { ok: false, error: "The API returned an unexpected ask payload." };
  }

  const sources: AskSource[] = [];
  for (const item of record.sources) {
    const parsed = parseAskSource(item);
    if (!parsed) {
      return {
        ok: false,
        error: "The API returned an unexpected ask source shape.",
      };
    }
    sources.push(parsed);
  }

  return {
    ok: true,
    result: {
      answer: record.answer,
      sources,
      model: record.model.trim(),
      grounded: record.grounded,
    },
  };
}
