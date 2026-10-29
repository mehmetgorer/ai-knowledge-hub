import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  releaseProcessLock,
  shouldApplyProcessFeedback,
  shouldRefreshDocumentsAfterProcess,
  tryAcquireProcessLock,
} from "./processing-ui-guards.ts";

describe("processing-ui-guards", () => {
  it("skips document refresh when selection moved to another collection", () => {
    assert.equal(shouldRefreshDocumentsAfterProcess("collection-b", "collection-a"), false);
    assert.equal(shouldRefreshDocumentsAfterProcess("collection-a", "collection-a"), true);
  });

  it("skips process feedback when selection no longer matches", () => {
    assert.equal(shouldApplyProcessFeedback("collection-b", "collection-a"), false);
    assert.equal(shouldApplyProcessFeedback("collection-a", "collection-a"), true);
  });

  it("allows only one in-flight process request per document id", () => {
    const inFlight = new Set<string>();
    assert.equal(tryAcquireProcessLock(inFlight, "doc-1"), true);
    assert.equal(tryAcquireProcessLock(inFlight, "doc-1"), false);
    releaseProcessLock(inFlight, "doc-1");
    assert.equal(tryAcquireProcessLock(inFlight, "doc-1"), true);
    releaseProcessLock(inFlight, "doc-1");
  });
});
