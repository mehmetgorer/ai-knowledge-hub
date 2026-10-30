import {
  dashboardSecondaryButtonClassName,
  documentStatusBadgeClassName,
} from "@/components/dashboard/ui";
import { formatDocumentStatus, type DocumentRecord } from "@/lib/api/client";
import {
  indexActionLabel,
  processActionLabel,
  shouldDisableDeleteButton,
  shouldDisableIndexButton,
  shouldDisableProcessButton,
  type RowActionState,
} from "@/lib/documents/document-ui-actions";

export type DocumentProcessFeedback =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; chunkCount: number }
  | { kind: "error"; message: string };

export type DocumentIndexFeedback =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; embeddedChunkCount: number; embeddingModel: string }
  | { kind: "error"; message: string };

export type DocumentDeleteFeedback =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success" }
  | { kind: "error"; message: string };

export type DocumentRowUiModel = {
  processLabel: string | null;
  indexLabel: string | null;
  processFeedback: DocumentProcessFeedback;
  indexFeedback: DocumentIndexFeedback;
  deleteFeedback: DocumentDeleteFeedback;
  disableProcess: boolean;
  disableIndex: boolean;
  disableDelete: boolean;
};

export function buildDocumentRowUiModel(
  document: DocumentRecord,
  documentsReady: boolean,
  processFeedbackByDocumentId: Record<string, DocumentProcessFeedback>,
  indexFeedbackByDocumentId: Record<string, DocumentIndexFeedback>,
  deleteFeedbackByDocumentId: Record<string, DocumentDeleteFeedback>,
): DocumentRowUiModel {
  const processFeedback = processFeedbackByDocumentId[document.id] ?? {
    kind: "idle" as const,
  };
  const indexFeedback = indexFeedbackByDocumentId[document.id] ?? {
    kind: "idle" as const,
  };
  const deleteFeedback = deleteFeedbackByDocumentId[document.id] ?? {
    kind: "idle" as const,
  };
  const rowActionState: RowActionState = {
    status: document.status,
    processFeedbackKind: processFeedback.kind,
    indexFeedbackKind: indexFeedback.kind,
    deleteFeedbackKind: deleteFeedback.kind,
    documentsReady,
  };
  return {
    processLabel: processActionLabel(document.status),
    indexLabel: indexActionLabel(document.status),
    processFeedback,
    indexFeedback,
    deleteFeedback,
    disableProcess: shouldDisableProcessButton(rowActionState),
    disableIndex: shouldDisableIndexButton(rowActionState),
    disableDelete: shouldDisableDeleteButton(rowActionState),
  };
}

export function DocumentStatusHints(props: { status: string }) {
  if (props.status === "PROCESSED") {
    return (
      <span className="mt-1 block text-xs text-zinc-500 dark:text-zinc-500">
        Chunks stored — index to enable search
      </span>
    );
  }
  if (props.status === "READY") {
    return (
      <span className="mt-1 block text-xs text-zinc-500 dark:text-zinc-500">
        Indexed — reprocess unavailable
      </span>
    );
  }
  return null;
}

type DocumentRowActionsProps = {
  document: DocumentRecord;
  model: DocumentRowUiModel;
  onProcess: () => void;
  onIndex: () => void;
  onDelete: () => void;
  /** Full-width stacked buttons (mobile cards). */
  compact?: boolean;
};

export function DocumentRowActions(props: DocumentRowActionsProps) {
  const { document, model } = props;
  const buttonClass = props.compact
    ? `${dashboardSecondaryButtonClassName} w-full px-3 py-2 text-xs`
    : `${dashboardSecondaryButtonClassName} w-full px-3 py-1.5 text-xs sm:w-auto`;

  return (
    <div
      className={
        props.compact
          ? "flex flex-col gap-2"
          : "flex min-w-[8rem] flex-col gap-1.5"
      }
    >
      {model.processLabel ? (
        <button
          type="button"
          className={buttonClass}
          disabled={model.disableProcess}
          aria-busy={model.processFeedback.kind === "loading"}
          onClick={props.onProcess}
        >
          {model.processFeedback.kind === "loading"
            ? "Processing…"
            : model.processLabel}
        </button>
      ) : document.status === "PROCESSING" ? (
        <span
          className="text-xs text-zinc-600 dark:text-zinc-400"
          role="status"
        >
          Processing…
        </span>
      ) : null}
      {model.indexLabel ? (
        <button
          type="button"
          className={buttonClass}
          disabled={model.disableIndex}
          aria-busy={model.indexFeedback.kind === "loading"}
          onClick={props.onIndex}
        >
          {model.indexFeedback.kind === "loading" ? "Indexing…" : model.indexLabel}
        </button>
      ) : document.status === "INDEXING" ? (
        <span
          className="text-xs text-zinc-600 dark:text-zinc-400"
          role="status"
        >
          Indexing…
        </span>
      ) : null}
      {model.processFeedback.kind === "success" ? (
        <p
          className="text-xs text-green-700 dark:text-green-400"
          role="status"
        >
          {model.processFeedback.chunkCount} chunk
          {model.processFeedback.chunkCount === 1 ? "" : "s"} from latest process
          run
        </p>
      ) : null}
      {model.indexFeedback.kind === "success" ? (
        <p
          className="text-xs text-green-700 dark:text-green-400"
          role="status"
        >
          {model.indexFeedback.embeddedChunkCount} embedding
          {model.indexFeedback.embeddedChunkCount === 1 ? "" : "s"} (
          {model.indexFeedback.embeddingModel}) from latest index run
        </p>
      ) : null}
      {model.processFeedback.kind === "error" ? (
        <p className="text-xs text-red-600 dark:text-red-400" role="alert">
          {model.processFeedback.message}
        </p>
      ) : null}
      {model.indexFeedback.kind === "error" ? (
        <p className="text-xs text-red-600 dark:text-red-400" role="alert">
          {model.indexFeedback.message}
        </p>
      ) : null}
      <button
        type="button"
        className={buttonClass}
        disabled={model.disableDelete}
        aria-busy={model.deleteFeedback.kind === "loading"}
        onClick={props.onDelete}
      >
        {model.deleteFeedback.kind === "loading" ? "Deleting…" : "Delete"}
      </button>
      {model.deleteFeedback.kind === "error" ? (
        <p className="text-xs text-red-600 dark:text-red-400" role="alert">
          {model.deleteFeedback.message}
        </p>
      ) : null}
    </div>
  );
}

export function DocumentStatusBadge(props: { status: string }) {
  return (
    <span className={documentStatusBadgeClassName(props.status)}>
      {formatDocumentStatus(props.status)}
    </span>
  );
}
