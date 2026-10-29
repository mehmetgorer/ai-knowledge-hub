/** Pure guards for semantic search race and stale-result avoidance. */

export function shouldApplySearchResults(input: {
  completedRequestId: number;
  activeRequestId: number;
  selectedCollectionId: string;
  collectionIdWhenSearchStarted: string;
  currentQueryFingerprint: string;
  queryFingerprintWhenSearchStarted: string;
}): boolean {
  return (
    input.completedRequestId === input.activeRequestId &&
    input.selectedCollectionId === input.collectionIdWhenSearchStarted &&
    input.currentQueryFingerprint === input.queryFingerprintWhenSearchStarted
  );
}

export function shouldDisplaySearchState(input: {
  searchStateKind: SearchViewStateKind;
  searchCollectionId: string | undefined;
  selectedCollectionId: string;
  currentQueryTrimmed: string;
  submittedQueryTrimmed: string;
}): boolean {
  if (input.searchStateKind === "idle") {
    return false;
  }
  if (
    !input.searchCollectionId ||
    input.searchCollectionId !== input.selectedCollectionId
  ) {
    return false;
  }
  if (input.currentQueryTrimmed !== input.submittedQueryTrimmed) {
    return false;
  }
  return true;
}

export type SearchViewStateKind =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "error";

export function shouldDisableSearchSubmit(input: {
  collectionSelected: boolean;
  queryValid: boolean;
  inFlight: boolean;
}): boolean {
  return (
    !input.collectionSelected || !input.queryValid || input.inFlight
  );
}

export function formatSearchPageNumbers(pageNumbers: number[]): string {
  if (pageNumbers.length === 0) {
    return "—";
  }
  return pageNumbers.join(", ");
}

export function formatCosineDistance(distance: number): string {
  return distance.toFixed(4);
}
