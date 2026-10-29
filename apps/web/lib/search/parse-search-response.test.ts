import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  parseSearchResponse,
  validateSearchQueryInput,
  validateSearchTopK,
} from "./parse-search-response.ts";

describe("parse-search-response", () => {
  it("validates non-empty trimmed queries", () => {
    assert.equal(validateSearchQueryInput("hello"), null);
    assert.equal(validateSearchQueryInput("   "), "Enter a non-empty search query.");
  });

  it("validates top_k options", () => {
    assert.equal(validateSearchTopK(3), true);
    assert.equal(validateSearchTopK(5), true);
    assert.equal(validateSearchTopK(10), true);
    assert.equal(validateSearchTopK(4), false);
    assert.equal(validateSearchTopK(0), false);
  });

  it("parses valid search matches", () => {
    const parsed = parseSearchResponse({
      matches: [
        {
          document_id: "doc-1",
          original_filename: "notes.txt",
          chunk_index: 2,
          text: "Passage text",
          source_kind: "text",
          page_numbers: [1, 2],
          cosine_distance: 0.12,
        },
      ],
    });
    assert.equal(parsed.ok, true);
    if (parsed.ok) {
      assert.equal(parsed.result.matches.length, 1);
      assert.equal(parsed.result.matches[0].chunk_index, 2);
    }
  });

  it("rejects malformed match payloads", () => {
    assert.equal(
      parseSearchResponse({ matches: [{ document_id: "x" }] }).ok,
      false,
    );
    assert.equal(parseSearchResponse({ matches: "bad" }).ok, false);
    assert.equal(parseSearchResponse(null).ok, false);
  });

  it("rejects non-finite cosine_distance", () => {
    const parsed = parseSearchResponse({
      matches: [
        {
          document_id: "d",
          original_filename: "a",
          chunk_index: 0,
          text: "t",
          source_kind: "text",
          page_numbers: [],
          cosine_distance: Number.NaN,
        },
      ],
    });
    assert.equal(parsed.ok, false);
  });

  it("accepts empty matches array", () => {
    const parsed = parseSearchResponse({ matches: [] });
    assert.equal(parsed.ok, true);
    if (parsed.ok) {
      assert.deepEqual(parsed.result.matches, []);
    }
  });
});
