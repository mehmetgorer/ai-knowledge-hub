import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  runSearchWithCoordinator,
  SearchRequestCoordinator,
} from "../search/search-request-lifecycle.ts";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

describe("ask-request-lifecycle", () => {
  it("handles collection A to B to A for ask requests", async () => {
    const coordinator = new SearchRequestCoordinator();
    let selectedCollectionId = "collection-a";
    const question = "What is JOIN?";
    const applied: string[] = [];

    const oldRequest = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: "collection-a",
      queryFingerprintWhenSearchStarted: question,
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => question,
      performSearch: async () => {
        await delay(40);
        return "old";
      },
      onApplied: (value) => {
        applied.push(value);
      },
    });

    coordinator.invalidatePending();
    selectedCollectionId = "collection-b";
    coordinator.invalidatePending();
    selectedCollectionId = "collection-a";

    const newRequest = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: "collection-a",
      queryFingerprintWhenSearchStarted: question,
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => question,
      performSearch: async () => "new",
      onApplied: (value) => {
        applied.push(value);
      },
    });

    assert.equal(await oldRequest, false);
    assert.equal(await newRequest, true);
    assert.deepEqual(applied, ["new"]);
  });

  it("does not clear inFlight when obsolete ask request completes", async () => {
    const coordinator = new SearchRequestCoordinator();
    const collectionId = "collection-a";
    const question = "q";

    const obsolete = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: collectionId,
      queryFingerprintWhenSearchStarted: question,
      readSelectedCollectionId: () => collectionId,
      readCurrentQueryFingerprint: () => question,
      performSearch: async () => {
        await delay(30);
        return "old";
      },
      onApplied: () => {},
    });

    coordinator.invalidatePending();
    const newerId = coordinator.beginRequest();
    assert.equal(coordinator.inFlight, true);

    await obsolete;
    assert.equal(coordinator.inFlight, true);

    coordinator.endRequest(newerId);
    assert.equal(coordinator.inFlight, false);
  });
});
