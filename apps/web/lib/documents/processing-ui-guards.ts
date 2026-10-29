/** Pure guards for DocumentsPanel process/list race avoidance (unit-testable). */

export function shouldRefreshDocumentsAfterProcess(
  selectedCollectionId: string,
  collectionIdWhenProcessStarted: string,
): boolean {
  return (
    selectedCollectionId.length > 0 &&
    selectedCollectionId === collectionIdWhenProcessStarted
  );
}

export function shouldApplyProcessFeedback(
  selectedCollectionId: string,
  collectionIdWhenProcessStarted: string,
): boolean {
  return selectedCollectionId === collectionIdWhenProcessStarted;
}

export function tryAcquireProcessLock(
  inFlightDocumentIds: Set<string>,
  documentId: string,
): boolean {
  if (inFlightDocumentIds.has(documentId)) {
    return false;
  }
  inFlightDocumentIds.add(documentId);
  return true;
}

export function releaseProcessLock(
  inFlightDocumentIds: Set<string>,
  documentId: string,
): void {
  inFlightDocumentIds.delete(documentId);
}
