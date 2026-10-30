import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { formatDocumentStatus } from "./format-document-status.ts";
import {
  buildDeleteConfirmationMessage,
  indexActionLabel,
  processActionLabel,
  shouldDisableDeleteButton,
  shouldDisableIndexButton,
  shouldDisableProcessButton,
} from "./document-ui-actions.ts";

describe("document-ui-actions", () => {
  it("maps process actions by document status", () => {
    assert.equal(processActionLabel("UPLOADED"), "Process");
    assert.equal(processActionLabel("FAILED"), "Retry");
    assert.equal(processActionLabel("PROCESSED"), "Reprocess");
    assert.equal(processActionLabel("READY"), null);
    assert.equal(processActionLabel("INDEXING"), null);
  });

  it("offers index only for processed documents", () => {
    assert.equal(indexActionLabel("PROCESSED"), "Index");
    assert.equal(indexActionLabel("UPLOADED"), null);
    assert.equal(indexActionLabel("READY"), null);
  });

  it("blocks duplicate or conflicting operations on the same row", () => {
    const base = {
      status: "PROCESSED",
      processFeedbackKind: "idle" as const,
      indexFeedbackKind: "idle" as const,
      deleteFeedbackKind: "idle" as const,
      documentsReady: true,
    };
    assert.equal(shouldDisableProcessButton(base), false);
    assert.equal(shouldDisableIndexButton(base), false);

    assert.equal(
      shouldDisableProcessButton({
        ...base,
        indexFeedbackKind: "loading",
      }),
      true,
    );
    assert.equal(
      shouldDisableIndexButton({
        ...base,
        processFeedbackKind: "loading",
      }),
      true,
    );
    assert.equal(
      shouldDisableProcessButton({
        ...base,
        processFeedbackKind: "loading",
      }),
      true,
    );
    assert.equal(
      shouldDisableIndexButton({
        ...base,
        indexFeedbackKind: "loading",
      }),
      true,
    );
  });

  it("includes INDEXING in formatDocumentStatus", () => {
    assert.equal(formatDocumentStatus("INDEXING"), "Indexing");
    assert.equal(formatDocumentStatus("READY"), "Indexed / Ready");
  });

  it("requires explicit confirmation copy for delete", () => {
    assert.match(
      buildDeleteConfirmationMessage("notes.txt"),
      /Delete "notes\.txt"/,
    );
    assert.match(buildDeleteConfirmationMessage("notes.txt"), /cannot be undone/);
  });

  it("disables delete while processing, indexing, or delete in flight", () => {
    const ready = {
      status: "UPLOADED",
      processFeedbackKind: "idle" as const,
      indexFeedbackKind: "idle" as const,
      deleteFeedbackKind: "idle" as const,
      documentsReady: true,
    };
    assert.equal(shouldDisableDeleteButton(ready), false);
    assert.equal(
      shouldDisableDeleteButton({ ...ready, status: "PROCESSING" }),
      true,
    );
    assert.equal(
      shouldDisableDeleteButton({ ...ready, status: "INDEXING" }),
      true,
    );
    assert.equal(
      shouldDisableDeleteButton({ ...ready, deleteFeedbackKind: "loading" }),
      true,
    );
  });
});
