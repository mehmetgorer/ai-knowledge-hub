import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  runSearchWithCoordinator,
  SearchRequestCoordinator,
} from "./search-request-lifecycle.ts";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

describe("search-request-lifecycle", () => {
  it("drops stale completion when collection changes before response", async () => {
    const coordinator = new SearchRequestCoordinator();
    let selectedCollectionId = "collection-a";
    const currentQuery = "hello";
    let applied: string | null = null;

    const slow = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: "collection-a",
      queryFingerprintWhenSearchStarted: "hello",
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => currentQuery,
      performSearch: async () => {
        selectedCollectionId = "collection-b";
        coordinator.invalidatePending();
        await delay(20);
        return "stale";
      },
      onApplied: (value) => {
        applied = value;
      },
    });

    assert.equal(await slow, false);
    assert.equal(applied, null);
    assert.equal(coordinator.inFlight, false);
  });

  it("allows new search after invalidating obsolete in-flight request", async () => {
    const coordinator = new SearchRequestCoordinator();
    let selectedCollectionId = "collection-a";
    const currentQuery = "shared";
    const applied: string[] = [];

    const first = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: "collection-a",
      queryFingerprintWhenSearchStarted: currentQuery,
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => currentQuery,
      performSearch: async () => {
        coordinator.invalidatePending();
        selectedCollectionId = "collection-b";
        await delay(30);
        return "first";
      },
      onApplied: (value) => {
        applied.push(value);
      },
    });

    selectedCollectionId = "collection-b";
    assert.equal(coordinator.inFlight, false);

    const second = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: "collection-b",
      queryFingerprintWhenSearchStarted: currentQuery,
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => currentQuery,
      performSearch: async () => "second",
      onApplied: (value) => {
        applied.push(value);
      },
    });

    assert.equal(await first, false);
    assert.equal(await second, true);
    assert.deepEqual(applied, ["second"]);
    assert.equal(coordinator.inFlight, false);
  });

  it("handles A to B to A without applying an older pending request", async () => {
    const coordinator = new SearchRequestCoordinator();
    let selectedCollectionId = "collection-a";
    const query = "find me";
    const applied: string[] = [];

    const oldRequest = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: "collection-a",
      queryFingerprintWhenSearchStarted: query,
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => query,
      performSearch: async () => {
        await delay(40);
        return "old-a";
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
      queryFingerprintWhenSearchStarted: query,
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => query,
      performSearch: async () => "new-a",
      onApplied: (value) => {
        applied.push(value);
      },
    });

    assert.equal(await oldRequest, false);
    assert.equal(await newRequest, true);
    assert.deepEqual(applied, ["new-a"]);
  });

  it("rejects completion when query changed after submit", async () => {
    const coordinator = new SearchRequestCoordinator();
    const selectedCollectionId = "collection-a";
    let currentQuery = "original";
    let applied = false;

    const finished = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: selectedCollectionId,
      queryFingerprintWhenSearchStarted: "original",
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => currentQuery,
      performSearch: async () => {
        currentQuery = "edited before response";
        await delay(10);
        return "hit";
      },
      onApplied: () => {
        applied = true;
      },
    });

    assert.equal(await finished, false);
    assert.equal(applied, false);
  });

  it("does not clear inFlight when an obsolete request finishes after a newer one started", async () => {
    const coordinator = new SearchRequestCoordinator();
    const selectedCollectionId = "collection-a";
    const query = "q";

    const obsolete = runSearchWithCoordinator({
      coordinator,
      collectionIdWhenSearchStarted: "collection-a",
      queryFingerprintWhenSearchStarted: query,
      readSelectedCollectionId: () => selectedCollectionId,
      readCurrentQueryFingerprint: () => query,
      performSearch: async () => {
        await delay(30);
        return "old";
      },
      onApplied: () => {},
    });

    coordinator.invalidatePending();
    const newerRequestId = coordinator.beginRequest();
    assert.equal(coordinator.inFlight, true);

    await obsolete;
    assert.equal(coordinator.inFlight, true);

    coordinator.endRequest(newerRequestId);
    assert.equal(coordinator.inFlight, false);
  });
});
