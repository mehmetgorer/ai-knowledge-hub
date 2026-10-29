"use client";

import { useCallback, useEffect, useId, useState } from "react";

import {
  authButtonClassName,
  authFieldClassName,
  authLabelClassName,
} from "@/components/auth-shell";
import {
  fetchCollections,
  fetchDocuments,
  formatDocumentStatus,
  uploadDocument,
  validateDocumentFile,
  type CollectionRecord,
  type DocumentRecord,
} from "@/lib/api/client";

type CollectionsLoadState =
  | { kind: "loading" }
  | { kind: "ready"; collections: CollectionRecord[] }
  | { kind: "error"; message: string };

type DocumentsLoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; documents: DocumentRecord[] }
  | { kind: "error"; message: string };

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString();
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function DocumentsPanel() {
  const collectionFieldId = useId();
  const fileFieldId = useId();

  const [collectionsState, setCollectionsState] = useState<CollectionsLoadState>(
    { kind: "loading" },
  );
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [documentsState, setDocumentsState] = useState<DocumentsLoadState>({
    kind: "idle",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [loadedForCollectionId, setLoadedForCollectionId] = useState<
    string | null
  >(null);

  const loadCollections = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setCollectionsState({ kind: "loading" });
    }
    const result = await fetchCollections();
    if (!result.ok) {
      setCollectionsState({ kind: "error", message: result.error.message });
      return;
    }
    setCollectionsState({ kind: "ready", collections: result.collections });
    setSelectedCollectionId((current) => {
      if (
        current &&
        result.collections.some((collection) => collection.id === current)
      ) {
        return current;
      }
      return result.collections[0]?.id ?? "";
    });
  }, []);

  const loadDocuments = useCallback(async (collectionId: string) => {
    if (!collectionId) {
      setDocumentsState({ kind: "idle" });
      setLoadedForCollectionId(null);
      return;
    }
    const result = await fetchDocuments(collectionId);
    if (!result.ok) {
      setDocumentsState({ kind: "error", message: result.error.message });
      return;
    }
    setDocumentsState({ kind: "ready", documents: result.documents });
    setLoadedForCollectionId(collectionId);
  }, []);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const result = await fetchCollections();
      if (cancelled) {
        return;
      }
      if (!result.ok) {
        setCollectionsState({ kind: "error", message: result.error.message });
        return;
      }
      setCollectionsState({ kind: "ready", collections: result.collections });
      setSelectedCollectionId(result.collections[0]?.id ?? "");
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedCollectionId) {
      return;
    }

    let cancelled = false;

    void (async () => {
      const result = await fetchDocuments(selectedCollectionId);
      if (cancelled) {
        return;
      }
      if (!result.ok) {
        setDocumentsState({ kind: "error", message: result.error.message });
        return;
      }
      setDocumentsState({ kind: "ready", documents: result.documents });
      setLoadedForCollectionId(selectedCollectionId);
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedCollectionId]);

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isUploading || !selectedCollectionId || !selectedFile) {
      return;
    }

    setUploadError(null);
    setUploadSuccess(null);

    const validationError = validateDocumentFile(selectedFile);
    if (validationError) {
      setUploadError(validationError);
      return;
    }

    setIsUploading(true);
    const result = await uploadDocument(selectedCollectionId, selectedFile);
    setIsUploading(false);

    if (!result.ok) {
      setUploadError(result.error.message);
      return;
    }

    setSelectedFile(null);
    setFileInputKey((key) => key + 1);
    setUploadSuccess(`“${result.document.original_filename}” uploaded.`);
    await loadDocuments(selectedCollectionId);
  }

  const collectionsReady =
    collectionsState.kind === "ready" && collectionsState.collections.length > 0;

  const documentsPendingForSelection =
    Boolean(selectedCollectionId) &&
    loadedForCollectionId !== selectedCollectionId;

  const showDocumentsSection = Boolean(selectedCollectionId);

  return (
    <section
      className="mt-8 space-y-6 rounded-lg border border-zinc-200 p-6 dark:border-zinc-800"
      aria-labelledby="documents-heading"
    >
      <div>
        <h2
          id="documents-heading"
          className="text-lg font-medium text-zinc-900 dark:text-zinc-50"
        >
          Documents
        </h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Upload PDF, TXT, or MD files (max 10 MB) into a collection. Status
          &quot;Uploaded&quot; means stored only — not processed for search yet.
        </p>
      </div>

      {collectionsState.kind === "loading" ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400" role="status">
          Loading collections…
        </p>
      ) : null}

      {collectionsState.kind === "error" ? (
        <div className="space-y-3">
          <p className="text-sm text-red-600 dark:text-red-400" role="alert">
            {collectionsState.message}
          </p>
          <button
            type="button"
            className="text-sm font-medium text-zinc-900 underline-offset-4 hover:underline dark:text-zinc-50"
            onClick={() => {
              void loadCollections();
            }}
          >
            Retry
          </button>
        </div>
      ) : null}

      {collectionsState.kind === "ready" &&
      collectionsState.collections.length === 0 ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400" role="status">
          Create a collection above before uploading documents.
        </p>
      ) : null}

      {collectionsReady ? (
        <>
          <form className="space-y-4" onSubmit={handleUpload}>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={collectionFieldId} className={authLabelClassName}>
                Collection
              </label>
              <select
                id={collectionFieldId}
                name="collectionId"
                value={selectedCollectionId}
                disabled={isUploading}
                onChange={(event) => {
                  setSelectedCollectionId(event.target.value);
                  setSelectedFile(null);
                  setUploadError(null);
                  setUploadSuccess(null);
                }}
                className={authFieldClassName}
              >
                {collectionsState.collections.map((collection) => (
                  <option key={collection.id} value={collection.id}>
                    {collection.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor={fileFieldId} className={authLabelClassName}>
                File
              </label>
              <input
                id={fileFieldId}
                name="file"
                type="file"
                accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
                disabled={isUploading}
                key={fileInputKey}
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedFile(file);
                  setUploadError(null);
                  setUploadSuccess(null);
                  if (file) {
                    const clientError = validateDocumentFile(file);
                    if (clientError) {
                      setUploadError(clientError);
                    }
                  }
                }}
                className={`${authFieldClassName} file:mr-3 file:rounded-md file:border-0 file:bg-zinc-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-zinc-900 dark:file:bg-zinc-800 dark:file:text-zinc-50`}
              />
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                PDF, TXT, or MD · maximum 10 MB
              </p>
            </div>

            <button
              type="submit"
              disabled={
                isUploading ||
                !selectedCollectionId ||
                !selectedFile ||
                documentsPendingForSelection
              }
              className={`${authButtonClassName} w-full sm:w-auto sm:min-w-[9rem]`}
            >
              {isUploading ? "Uploading…" : "Upload"}
            </button>
          </form>

          {uploadError ? (
            <p className="text-sm text-red-600 dark:text-red-400" role="alert">
              {uploadError}
            </p>
          ) : null}

          {uploadSuccess ? (
            <p
              className="text-sm text-green-700 dark:text-green-400"
              role="status"
            >
              {uploadSuccess}
            </p>
          ) : null}

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
              Files in this collection
            </h3>

            {documentsPendingForSelection ? (
              <p
                className="text-sm text-zinc-600 dark:text-zinc-400"
                role="status"
              >
                Loading documents…
              </p>
            ) : null}

            {!documentsPendingForSelection &&
            documentsState.kind === "error" &&
            showDocumentsSection ? (
              <div className="space-y-3">
                <p
                  className="text-sm text-red-600 dark:text-red-400"
                  role="alert"
                >
                  {documentsState.message}
                </p>
                <button
                  type="button"
                  className="text-sm font-medium text-zinc-900 underline-offset-4 hover:underline dark:text-zinc-50"
                  onClick={() => {
                    void loadDocuments(selectedCollectionId);
                  }}
                >
                  Retry
                </button>
              </div>
            ) : null}

            {!documentsPendingForSelection &&
            documentsState.kind === "ready" &&
            showDocumentsSection &&
            documentsState.documents.length === 0 ? (
              <p
                className="text-sm text-zinc-600 dark:text-zinc-400"
                role="status"
              >
                No documents in this collection yet.
              </p>
            ) : null}

            {!documentsPendingForSelection &&
            documentsState.kind === "ready" &&
            showDocumentsSection &&
            documentsState.documents.length > 0 ? (
              <div className="overflow-x-auto rounded-md border border-zinc-200 dark:border-zinc-800">
                <table className="min-w-full text-left text-sm">
                  <caption className="sr-only">
                    Documents in the selected collection
                  </caption>
                  <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-400">
                    <tr>
                      <th scope="col" className="px-4 py-2 font-medium">
                        Name
                      </th>
                      <th scope="col" className="px-4 py-2 font-medium">
                        Size
                      </th>
                      <th scope="col" className="px-4 py-2 font-medium">
                        Status
                      </th>
                      <th scope="col" className="px-4 py-2 font-medium">
                        Uploaded
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                    {documentsState.documents.map((document) => (
                      <tr key={document.id}>
                        <td className="px-4 py-3 font-medium text-zinc-900 dark:text-zinc-50">
                          {document.original_filename}
                        </td>
                        <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">
                          {formatFileSize(document.size_bytes)}
                        </td>
                        <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">
                          {formatDocumentStatus(document.status)}
                        </td>
                        <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">
                          {formatTimestamp(document.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
