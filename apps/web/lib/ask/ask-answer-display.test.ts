import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  buildSourceLookup,
  splitAnswerForDisplay,
} from "./ask-answer-display.ts";

describe("ask-answer-display", () => {
  it("associates inline citations with known source ids", () => {
    const parts = splitAnswerForDisplay(
      "See [S1] and [S2] for details.",
      new Set(["S1", "S2"]),
    );
    const citations = parts.filter((part) => part.kind === "citation");
    assert.equal(citations.length, 2);
    assert.deepEqual(
      citations.map((part) => (part.kind === "citation" ? part.known : false)),
      [true, true],
    );
  });

  it("marks unknown citation markers without inventing metadata", () => {
    const parts = splitAnswerForDisplay("See [S9].", new Set(["S1"]));
    const cite = parts.find((part) => part.kind === "citation");
    assert.equal(cite && cite.kind === "citation" && cite.known, false);
  });

  it("builds source lookup by source_id", () => {
    const map = buildSourceLookup([
      {
        source_id: "S1",
        document_id: "d",
        original_filename: "a.txt",
        chunk_index: 0,
        page_numbers: [1],
        text: "t",
        cosine_distance: 0.1,
      },
    ]);
    assert.equal(map.get("S1")?.original_filename, "a.txt");
  });
});
