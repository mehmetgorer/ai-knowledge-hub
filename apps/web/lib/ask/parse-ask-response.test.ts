import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  parseAskResponse,
  validateAskQuestionInput,
} from "./parse-ask-response.ts";

describe("parse-ask-response", () => {
  it("validates non-empty questions", () => {
    assert.equal(validateAskQuestionInput("  "), "Enter a non-empty question.");
    assert.equal(validateAskQuestionInput("hello"), null);
  });

  it("parses grounded ask response with sources", () => {
    const parsed = parseAskResponse({
      answer: "JOIN merges rows [S1].",
      model: "qwen3:1.7b",
      grounded: true,
      sources: [
        {
          source_id: "S1",
          document_id: "doc-1",
          original_filename: "db.txt",
          chunk_index: 0,
          page_numbers: [1],
          text: "JOIN combines tables.",
          cosine_distance: 0.16,
        },
      ],
    });
    assert.equal(parsed.ok, true);
    if (parsed.ok) {
      assert.equal(parsed.result.grounded, true);
      assert.equal(parsed.result.sources[0]?.source_id, "S1");
    }
  });

  it("parses ungrounded response with empty sources", () => {
    const parsed = parseAskResponse({
      answer: "Not enough evidence.",
      model: "qwen3:1.7b",
      grounded: false,
      sources: [],
    });
    assert.equal(parsed.ok, true);
    if (parsed.ok) {
      assert.equal(parsed.result.grounded, false);
      assert.equal(parsed.result.sources.length, 0);
    }
  });

  it("rejects malformed source metadata", () => {
    assert.equal(
      parseAskResponse({
        answer: "x",
        model: "m",
        grounded: true,
        sources: [{ source_id: "bad", document_id: "d" }],
      }).ok,
      false,
    );
    assert.equal(parseAskResponse(null).ok, false);
    assert.equal(
      parseAskResponse({ answer: 1, model: "m", grounded: false, sources: [] })
        .ok,
      false,
    );
  });
});
