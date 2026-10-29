/** Pure helpers for DocumentsPanel status labels and action button state. */

export type DocumentFeedbackKind = "idle" | "loading" | "success" | "error";

export type RowActionState = {
  status: string;
  processFeedbackKind: DocumentFeedbackKind;
  indexFeedbackKind: DocumentFeedbackKind;
  documentsReady: boolean;
};

export function processActionLabel(status: string): string | null {
  switch (status) {
    case "UPLOADED":
      return "Process";
    case "FAILED":
      return "Retry";
    case "PROCESSED":
      return "Reprocess";
    default:
      return null;
  }
}

export function indexActionLabel(status: string): string | null {
  if (status === "PROCESSED") {
    return "Index";
  }
  return null;
}

export function shouldDisableProcessButton(state: RowActionState): boolean {
  if (!state.documentsReady) {
    return true;
  }
  if (state.status === "PROCESSING") {
    return true;
  }
  if (state.processFeedbackKind === "loading") {
    return true;
  }
  if (state.indexFeedbackKind === "loading") {
    return true;
  }
  return false;
}

export function shouldDisableIndexButton(state: RowActionState): boolean {
  if (!state.documentsReady) {
    return true;
  }
  if (state.status !== "PROCESSED") {
    return true;
  }
  if (state.indexFeedbackKind === "loading") {
    return true;
  }
  if (state.processFeedbackKind === "loading") {
    return true;
  }
  return false;
}
