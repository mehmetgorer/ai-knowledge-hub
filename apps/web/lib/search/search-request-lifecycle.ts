/** Search request generation and in-flight locking (DocumentsPanel lifecycle). */

export type SearchCompletionContext = {
  selectedCollectionId: string;
  collectionIdWhenSearchStarted: string;
  currentQueryFingerprint: string;
  queryFingerprintWhenSearchStarted: string;
};

export class SearchRequestCoordinator {
  private activeRequestId = 0;

  inFlight = false;

  invalidatePending(): number {
    this.activeRequestId += 1;
    this.inFlight = false;
    return this.activeRequestId;
  }

  beginRequest(): number {
    this.activeRequestId += 1;
    this.inFlight = true;
    return this.activeRequestId;
  }

  shouldApplyCompletion(
    completedRequestId: number,
    context: SearchCompletionContext,
  ): boolean {
    return (
      completedRequestId === this.activeRequestId &&
      context.selectedCollectionId === context.collectionIdWhenSearchStarted &&
      context.currentQueryFingerprint ===
        context.queryFingerprintWhenSearchStarted
    );
  }

  endRequest(completedRequestId: number): void {
    if (this.activeRequestId === completedRequestId) {
      this.inFlight = false;
    }
  }

  get activeGeneration(): number {
    return this.activeRequestId;
  }
}

export async function runSearchWithCoordinator<T>(input: {
  coordinator: SearchRequestCoordinator;
  collectionIdWhenSearchStarted: string;
  queryFingerprintWhenSearchStarted: string;
  readSelectedCollectionId: () => string;
  readCurrentQueryFingerprint: () => string;
  performSearch: () => Promise<T>;
  onApplied: (value: T) => void;
}): Promise<boolean> {
  const requestId = input.coordinator.beginRequest();
  try {
    const value = await input.performSearch();
    if (
      !input.coordinator.shouldApplyCompletion(requestId, {
        selectedCollectionId: input.readSelectedCollectionId(),
        collectionIdWhenSearchStarted: input.collectionIdWhenSearchStarted,
        currentQueryFingerprint: input.readCurrentQueryFingerprint(),
        queryFingerprintWhenSearchStarted: input.queryFingerprintWhenSearchStarted,
      })
    ) {
      return false;
    }
    input.onApplied(value);
    return true;
  } finally {
    input.coordinator.endRequest(requestId);
  }
}
