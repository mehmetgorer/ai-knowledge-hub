import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  askGroundingStatusLabel,
  shouldDisableAskSubmit,
  shouldDisplayAskState,
} from "./ask-ui-guards.ts";

describe("ask-ui-guards", () => {
  it("hides stale ask state on collection or question mismatch", () => {
    assert.equal(
      shouldDisplayAskState({
        askStateKind: "ready",
        askCollectionId: "a",
        selectedCollectionId: "a",
        currentQuestionTrimmed: "q",
        submittedQuestionTrimmed: "q",
      }),
      true,
    );
    assert.equal(
      shouldDisplayAskState({
        askStateKind: "ready",
        askCollectionId: "a",
        selectedCollectionId: "b",
        currentQuestionTrimmed: "q",
        submittedQuestionTrimmed: "q",
      }),
      false,
    );
    assert.equal(
      shouldDisplayAskState({
        askStateKind: "loading",
        askCollectionId: "a",
        selectedCollectionId: "a",
        currentQuestionTrimmed: "edited",
        submittedQuestionTrimmed: "original",
      }),
      false,
    );
  });

  it("disables submit while in flight or invalid question", () => {
    assert.equal(
      shouldDisableAskSubmit({
        collectionSelected: true,
        questionValid: true,
        inFlight: true,
      }),
      true,
    );
    assert.equal(
      shouldDisableAskSubmit({
        collectionSelected: true,
        questionValid: false,
        inFlight: false,
      }),
      true,
    );
  });

  it("labels grounding without implying fact-checking", () => {
    assert.match(askGroundingStatusLabel(true), /structural validation/);
    assert.match(askGroundingStatusLabel(false), /Not supported/);
  });
});
