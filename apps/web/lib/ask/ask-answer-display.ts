/** Safe text segmentation for inline [Sx] citation markers. */

export type AnswerDisplayPart =
  | { kind: "text"; value: string }
  | { kind: "citation"; sourceId: string; known: boolean };

const CITATION_PATTERN = /\[(S\d+)\]/g;

export function splitAnswerForDisplay(
  answer: string,
  knownSourceIds: ReadonlySet<string>,
): AnswerDisplayPart[] {
  const parts: AnswerDisplayPart[] = [];
  let lastIndex = 0;
  for (const match of answer.matchAll(CITATION_PATTERN)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      parts.push({
        kind: "text",
        value: answer.slice(lastIndex, index),
      });
    }
    const sourceId = match[1];
    parts.push({
      kind: "citation",
      sourceId,
      known: knownSourceIds.has(sourceId),
    });
    lastIndex = index + match[0].length;
  }
  if (lastIndex < answer.length) {
    parts.push({ kind: "text", value: answer.slice(lastIndex) });
  }
  if (parts.length === 0) {
    parts.push({ kind: "text", value: answer });
  }
  return parts;
}

export function buildSourceLookup<T extends { source_id: string }>(
  sources: readonly T[],
): Map<string, T> {
  const map = new Map<string, T>();
  for (const source of sources) {
    map.set(source.source_id, source);
  }
  return map;
}
