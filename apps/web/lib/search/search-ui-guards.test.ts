import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  formatCosineDistance,
  formatSearchPageNumbers,
  shouldApplySearchResults,
  shouldDisableSearchSubmit,
  shouldDisplaySearchState,
} from "./search-ui-guards.ts";

describe("search-ui-guards", () => {
  it("applies results only for matching request, collection and query", () => {
    const base = {
      completedRequestId: 2,
      activeRequestId: 2,
      selectedCollectionId: "collection-a",
      collectionIdWhenSearchStarted: "collection-a",
      currentQueryFingerprint: "hello",
      queryFingerprintWhenSearchStarted: "hello",
    };
    assert.equal(shouldApplySearchResults(base), true);
    assert.equal(
      shouldApplySearchResults({ ...base, activeRequestId: 3 }),
      false,
    );
    assert.equal(
      shouldApplySearchResults({
        ...base,
        selectedCollectionId: "collection-b",
      }),
      false,
    );
    assert.equal(
      shouldApplySearchResults({
        ...base,
        currentQueryFingerprint: "changed",
      }),
      false,
    );
  });

  it("handles collection switch A to B to A with stale request ids", () => {
    assert.equal(
      shouldApplySearchResults({
        completedRequestId: 1,
        activeRequestId: 2,
        selectedCollectionId: "collection-a",
        collectionIdWhenSearchStarted: "collection-a",
        currentQueryFingerprint: "q",
        queryFingerprintWhenSearchStarted: "q",
      }),
      false,
    );
  });

  it("hides stale results when query or collection no longer matches", () => {
    assert.equal(
      shouldDisplaySearchState({
        searchStateKind: "ready",
        searchCollectionId: "collection-a",
        selectedCollectionId: "collection-a",
        currentQueryTrimmed: "hello",
        submittedQueryTrimmed: "hello",
      }),
      true,
    );
    assert.equal(
      shouldDisplaySearchState({
        searchStateKind: "ready",
        searchCollectionId: "collection-a",
        selectedCollectionId: "collection-b",
        currentQueryTrimmed: "hello",
        submittedQueryTrimmed: "hello",
      }),
      false,
    );
    assert.equal(
      shouldDisplaySearchState({
        searchStateKind: "ready",
        searchCollectionId: "collection-a",
        selectedCollectionId: "collection-a",
        currentQueryTrimmed: "edited",
        submittedQueryTrimmed: "hello",
      }),
      false,
    );
  });

  it("disables submit while in flight or invalid query", () => {
    assert.equal(
      shouldDisableSearchSubmit({
        collectionSelected: true,
        queryValid: true,
        inFlight: false,
      }),
      false,
    );
    assert.equal(
      shouldDisableSearchSubmit({
        collectionSelected: true,
        queryValid: true,
        inFlight: true,
      }),
      true,
    );
    assert.equal(
      shouldDisableSearchSubmit({
        collectionSelected: true,
        queryValid: false,
        inFlight: false,
      }),
      true,
    );
  });

  it("formats display metadata", () => {
    assert.equal(formatSearchPageNumbers([2, 3]), "2, 3");
    assert.equal(formatSearchPageNumbers([]), "—");
    assert.equal(formatCosineDistance(0.123456), "0.1235");
  });
});
