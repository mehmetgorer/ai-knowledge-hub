/** Human-readable document status labels for dashboard UI. */

export function formatDocumentStatus(status: string): string {
  switch (status) {
    case "UPLOADED":
      return "Uploaded";
    case "PROCESSING":
      return "Processing";
    case "PROCESSED":
      return "Processed";
    case "INDEXING":
      return "Indexing";
    case "READY":
      return "Indexed / Ready";
    case "FAILED":
      return "Failed";
    default:
      return status;
  }
}
