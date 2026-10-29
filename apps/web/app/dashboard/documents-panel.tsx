"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import {
  authButtonClassName,
  authFieldClassName,
  authLabelClassName,
} from "@/components/auth-shell";
import {
  fetchCollections,
  fetchDocuments,
  formatDocumentStatus,
  indexDocument,
  processDocument,
  searchCollection,
  uploadDocument,
  validateDocumentFile,
  type CollectionRecord,
  type DocumentRecord,
  type SearchMatch,
  SEARCH_TOP_K_OPTIONS,
} from "@/lib/api/client";
import {
  formatCosineDistance,
  formatSearchPageNumbers,
  shouldApplySearchResults,
  shouldDisableSearchSubmit,
  shouldDisplaySearchState,
} from "@/lib/search/search-ui-guards";
import { validateSearchQueryInput } from "@/lib/search/parse-search-response";
import {
  indexActionLabel,
  processActionLabel,
  shouldDisableIndexButton,
  shouldDisableProcessButton,
} from "@/lib/documents/document-ui-actions";
import {
  releaseProcessLock,
  shouldApplyProcessFeedback,
  shouldRefreshDocumentsAfterProcess,
  tryAcquireProcessLock,
} from "@/lib/documents/processing-ui-guards";

type CollectionsLoadState =
  | { kind: "loading" }
  | { kind: "ready"; collections: CollectionRecord[] }
  | { kind: "error"; message: string };

type DocumentsLoadState =
  | { kind: "idle" }
  | { kind: "loading"; collectionId: string }
  | { kind: "ready"; collectionId: string; documents: DocumentRecord[] }
  | { kind: "error"; collectionId: string; message: string };

type DocumentsViewState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; documents: DocumentRecord[] }
  | { kind: "error"; message: string };

type DocumentProcessFeedback =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; chunkCount: number }
  | { kind: "error"; message: string };

type DocumentIndexFeedback =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; embeddedChunkCount: number; embeddingModel: string }
  | { kind: "error"; message: string };

type SearchViewState =
  | { kind: "idle" }
  | { kind: "loading"; collectionId: string }
  | {
      kind: "ready";
      collectionId: string;
      query: string;
      matches: SearchMatch[];
    }
  | { kind: "empty"; collectionId: string; query: string }
  | { kind: "error"; collectionId: string; query: string; message: string };

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

function documentsViewForSelection(
  selectedCollectionId: string,
  documentsState: DocumentsLoadState,
): DocumentsViewState {
  if (!selectedCollectionId) {
    return { kind: "idle" };
  }
  if (documentsState.kind === "idle") {
    return { kind: "loading" };
  }
  if (documentsState.collectionId !== selectedCollectionId) {
    return { kind: "loading" };
  }
  if (documentsState.kind === "loading") {
    return { kind: "loading" };
  }
  if (documentsState.kind === "error") {
    return { kind: "error", message: documentsState.message };
  }
  return { kind: "ready", documents: documentsState.documents };
}

export function DocumentsPanel() {
  const collectionFieldId = useId();
  const fileFieldId = useId();
  const searchQueryFieldId = useId();
  const searchTopKFieldId = useId();

  const [collectionsState, setCollectionsState] = useState<CollectionsLoadState>(
    { kind: "loading" },
  );
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const documentsRequestIdRef = useRef(0);
  const searchRequestIdRef = useRef(0);
  const searchInFlightRef = useRef(false);
  const processingDocumentIdsRef = useRef<Set<string>>(new Set());
  const selectedCollectionIdRef = useRef(selectedCollectionId);

  useEffect(() => {
    selectedCollectionIdRef.current = selectedCollectionId;
  }, [selectedCollectionId]);

  const [documentsState, setDocumentsState] = useState<DocumentsLoadState>({
    kind: "idle",
  });
  const [processFeedbackByDocumentId, setProcessFeedbackByDocumentId] = useState<
    Record<string, DocumentProcessFeedback>
  >({});
  const [indexFeedbackByDocumentId, setIndexFeedbackByDocumentId] = useState<
    Record<string, DocumentIndexFeedback>
  >({});
  const [searchQuery, setSearchQuery] = useState("");
  const [submittedSearchQuery, setSubmittedSearchQuery] = useState("");
  const [searchTopK, setSearchTopK] = useState<3 | 5 | 10>(5);
  const [searchState, setSearchState] = useState<SearchViewState>({
    kind: "idle",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [fileInputKey, setFileInputKey] = useState(0);

  const runDocumentsFetch = useCallback(
    (collectionId: string, requestId: number): Promise<void> => {
      return (async () => {
        setDocumentsState({ kind: "loading", collectionId });

        const result = await fetchDocuments(collectionId);
        if (documentsRequestIdRef.current !== requestId) {
          return;
        }

        if (!result.ok) {
          setDocumentsState({
            kind: "error",
            collectionId,
            message: result.error.message,
          });
          return;
        }

        setDocumentsState({
          kind: "ready",
          collectionId,
          documents: result.documents,
        });
      })();
    },
    [],
  );

  const retryDocumentsLoad = useCallback(() => {
    if (!selectedCollectionId) {
      return;
    }
    const requestId = ++documentsRequestIdRef.current;
    void runDocumentsFetch(selectedCollectionId, requestId);
  }, [selectedCollectionId, runDocumentsFetch]);

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
    const requestId = ++documentsRequestIdRef.current;
    void runDocumentsFetch(selectedCollectionId, requestId);
  }, [selectedCollectionId, runDocumentsFetch]);

  const runProcessDocument = useCallback(
    async (documentId: string) => {
      const collectionIdAtStart = selectedCollectionIdRef.current;
      if (!collectionIdAtStart) {
        return;
      }
      if (!tryAcquireProcessLock(processingDocumentIdsRef.current, documentId)) {
        return;
      }

      setProcessFeedbackByDocumentId((current) => ({
        ...current,
        [documentId]: { kind: "loading" },
      }));

      try {
        const result = await processDocument(collectionIdAtStart, documentId);

        const selectedNow = selectedCollectionIdRef.current;
        if (
          shouldRefreshDocumentsAfterProcess(selectedNow, collectionIdAtStart)
        ) {
          const requestId = ++documentsRequestIdRef.current;
          await runDocumentsFetch(collectionIdAtStart, requestId);
        }

        if (
          !shouldApplyProcessFeedback(
            selectedCollectionIdRef.current,
            collectionIdAtStart,
          )
        ) {
          setProcessFeedbackByDocumentId((current) => {
            if (!(documentId in current)) {
              return current;
            }
            const next = { ...current };
            delete next[documentId];
            return next;
          });
          return;
        }

        if (!result.ok) {
          setProcessFeedbackByDocumentId((current) => ({
            ...current,
            [documentId]: { kind: "error", message: result.error.message },
          }));
          return;
        }

        setProcessFeedbackByDocumentId((current) => ({
          ...current,
          [documentId]: {
            kind: "success",
            chunkCount: result.process.chunk_count,
          },
        }));
      } finally {
        releaseProcessLock(processingDocumentIdsRef.current, documentId);
      }
    },
    [runDocumentsFetch],
  );

  const runIndexDocument = useCallback(
    async (documentId: string) => {
      const collectionIdAtStart = selectedCollectionIdRef.current;
      if (!collectionIdAtStart) {
        return;
      }
      if (!tryAcquireProcessLock(processingDocumentIdsRef.current, documentId)) {
        return;
      }

      setIndexFeedbackByDocumentId((current) => ({
        ...current,
        [documentId]: { kind: "loading" },
      }));

      try {
        const result = await indexDocument(collectionIdAtStart, documentId);

        const selectedNow = selectedCollectionIdRef.current;
        if (
          shouldRefreshDocumentsAfterProcess(selectedNow, collectionIdAtStart)
        ) {
          const requestId = ++documentsRequestIdRef.current;
          await runDocumentsFetch(collectionIdAtStart, requestId);
        }

        if (
          !shouldApplyProcessFeedback(
            selectedCollectionIdRef.current,
            collectionIdAtStart,
          )
        ) {
          setIndexFeedbackByDocumentId((current) => {
            if (!(documentId in current)) {
              return current;
            }
            const next = { ...current };
            delete next[documentId];
            return next;
          });
          return;
        }

        if (!result.ok) {
          setIndexFeedbackByDocumentId((current) => ({
            ...current,
            [documentId]: { kind: "error", message: result.error.message },
          }));
          return;
        }

        setIndexFeedbackByDocumentId((current) => ({
          ...current,
          [documentId]: {
            kind: "success",
            embeddedChunkCount: result.index.embedded_chunk_count,
            embeddingModel: result.index.embedding_model,
          },
        }));
      } finally {
        releaseProcessLock(processingDocumentIdsRef.current, documentId);
      }
    },
    [runDocumentsFetch],
  );

  const runCollectionSearch = useCallback(async () => {
    const collectionIdAtStart = selectedCollectionIdRef.current;
    if (!collectionIdAtStart || searchInFlightRef.current) {
      return;
    }

    const queryError = validateSearchQueryInput(searchQuery);
    if (queryError) {
      setSearchState({
        kind: "error",
        collectionId: collectionIdAtStart,
        query: searchQuery.trim(),
        message: queryError,
      });
      return;
    }

    const queryFingerprint = searchQuery.trim();
    setSubmittedSearchQuery(queryFingerprint);
    searchInFlightRef.current = true;
    const requestId = ++searchRequestIdRef.current;
    setSearchState({ kind: "loading", collectionId: collectionIdAtStart });

    try {
      const result = await searchCollection(
        collectionIdAtStart,
        queryFingerprint,
        searchTopK,
      );

      if (
        !shouldApplySearchResults({
          completedRequestId: requestId,
          activeRequestId: searchRequestIdRef.current,
          selectedCollectionId: selectedCollectionIdRef.current,
          collectionIdWhenSearchStarted: collectionIdAtStart,
          currentQueryFingerprint: queryFingerprint,
          queryFingerprintWhenSearchStarted: queryFingerprint,
        })
      ) {
        return;
      }

      if (!result.ok) {
        setSearchState({
          kind: "error",
          collectionId: collectionIdAtStart,
          query: queryFingerprint,
          message: result.error.message,
        });
        return;
      }

      if (result.search.matches.length === 0) {
        setSearchState({
          kind: "empty",
          collectionId: collectionIdAtStart,
          query: queryFingerprint,
        });
        return;
      }

      setSearchState({
        kind: "ready",
        collectionId: collectionIdAtStart,
        query: queryFingerprint,
        matches: result.search.matches,
      });
    } finally {
      searchInFlightRef.current = false;
    }
  }, [searchQuery, searchTopK]);

  const showSearchFeedback = shouldDisplaySearchState({
    searchStateKind: searchState.kind,
    searchCollectionId:
      searchState.kind === "idle" ? undefined : searchState.collectionId,
    selectedCollectionId,
    currentQueryTrimmed: searchQuery.trim(),
    submittedQueryTrimmed: submittedSearchQuery,
  });

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
    const requestId = ++documentsRequestIdRef.current;
    await runDocumentsFetch(selectedCollectionId, requestId);
  }

  const collectionsReady =
    collectionsState.kind === "ready" && collectionsState.collections.length > 0;

  const documentsView = documentsViewForSelection(
    selectedCollectionId,
    documentsState,
  );

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
          Upload PDF, TXT, or MD files (max 10 MB) into a collection.{" "}
          <strong className="font-medium">Process</strong> extracts text and
          stores chunks; <strong className="font-medium">Index</strong> runs
          local embedding on processed chunks (first run may take longer while
          the model initializes). Use semantic search below to find passages in
          indexed (Ready) documents — not AI-generated answers.
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
                  setProcessFeedbackByDocumentId({});
                  setIndexFeedbackByDocumentId({});
                  setSearchQuery("");
                  setSubmittedSearchQuery("");
                  setSearchState({ kind: "idle" });
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
                documentsView.kind === "loading"
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

          <div className="space-y-3 rounded-md border border-zinc-200 p-4 dark:border-zinc-800">
            <div>
              <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                Semantic search
              </h3>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                Searches indexed (Ready) documents in the selected collection
                only. Results are relevant passages ranked by cosine distance
                (lower is closer) — not answer confidence or generated text.
              </p>
            </div>
            <form
              className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end"
              onSubmit={(event) => {
                event.preventDefault();
                void runCollectionSearch();
              }}
            >
              <div className="flex min-w-[12rem] flex-1 flex-col gap-1.5">
                <label
                  htmlFor={searchQueryFieldId}
                  className={authLabelClassName}
                >
                  Query
                </label>
                <input
                  id={searchQueryFieldId}
                  name="searchQuery"
                  type="text"
                  value={searchQuery}
                  disabled={searchState.kind === "loading"}
                  onChange={(event) => {
                    setSearchQuery(event.target.value);
                  }}
                  className={authFieldClassName}
                  autoComplete="off"
                />
              </div>
              <div className="flex w-full flex-col gap-1.5 sm:w-auto">
                <label htmlFor={searchTopKFieldId} className={authLabelClassName}>
                  Results
                </label>
                <select
                  id={searchTopKFieldId}
                  name="searchTopK"
                  value={searchTopK}
                  disabled={searchState.kind === "loading"}
                  onChange={(event) => {
                    setSearchTopK(Number(event.target.value) as 3 | 5 | 10);
                  }}
                  className={authFieldClassName}
                >
                  {SEARCH_TOP_K_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      Top {value}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="submit"
                disabled={shouldDisableSearchSubmit({
                  collectionSelected: Boolean(selectedCollectionId),
                  queryValid: validateSearchQueryInput(searchQuery) === null,
                  inFlight: searchState.kind === "loading",
                })}
                className={`${authButtonClassName} w-full sm:w-auto sm:min-w-[9rem]`}
                aria-busy={searchState.kind === "loading"}
              >
                {searchState.kind === "loading" ? "Searching…" : "Search"}
              </button>
            </form>

            {searchState.kind === "loading" &&
            searchState.collectionId === selectedCollectionId &&
            showSearchFeedback ? (
              <p
                className="text-sm text-zinc-600 dark:text-zinc-400"
                role="status"
              >
                Searching indexed chunks…
              </p>
            ) : null}

            {searchState.kind === "error" &&
            searchState.collectionId === selectedCollectionId &&
            showSearchFeedback ? (
              <div className="space-y-2">
                <p
                  className="text-sm text-red-600 dark:text-red-400"
                  role="alert"
                >
                  {searchState.message}
                </p>
                <button
                  type="button"
                  className="text-sm font-medium text-zinc-900 underline-offset-4 hover:underline dark:text-zinc-50"
                  onClick={() => {
                    void runCollectionSearch();
                  }}
                >
                  Retry search
                </button>
              </div>
            ) : null}

            {searchState.kind === "empty" &&
            searchState.collectionId === selectedCollectionId &&
            showSearchFeedback ? (
              <p
                className="text-sm text-zinc-600 dark:text-zinc-400"
                role="status"
              >
                No matching indexed passages for &quot;{searchState.query}&quot;.
              </p>
            ) : null}

            {searchState.kind === "ready" &&
            searchState.collectionId === selectedCollectionId &&
            showSearchFeedback ? (
              <ol className="space-y-3">
                {searchState.matches.map((match, index) => (
                  <li
                    key={`${match.document_id}-${match.chunk_index}-${index}`}
                    className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800"
                  >
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                      {match.original_filename}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">
                      {match.text}
                    </p>
                    <dl className="mt-2 grid gap-1 text-xs text-zinc-500 dark:text-zinc-400 sm:grid-cols-2">
                      <div>
                        <dt className="inline font-medium">Chunk: </dt>
                        <dd className="inline">{match.chunk_index}</dd>
                      </div>
                      <div>
                        <dt className="inline font-medium">Pages: </dt>
                        <dd className="inline">
                          {formatSearchPageNumbers(match.page_numbers)}
                        </dd>
                      </div>
                      <div>
                        <dt className="inline font-medium">Source: </dt>
                        <dd className="inline">{match.source_kind}</dd>
                      </div>
                      <div>
                        <dt className="inline font-medium">Distance: </dt>
                        <dd className="inline">
                          {formatCosineDistance(match.cosine_distance)}
                        </dd>
                      </div>
                    </dl>
                  </li>
                ))}
              </ol>
            ) : null}
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
              Files in this collection
            </h3>

            {documentsView.kind === "loading" ? (
              <p
                className="text-sm text-zinc-600 dark:text-zinc-400"
                role="status"
              >
                Loading documents…
              </p>
            ) : null}

            {documentsView.kind === "error" ? (
              <div className="space-y-3">
                <p
                  className="text-sm text-red-600 dark:text-red-400"
                  role="alert"
                >
                  {documentsView.message}
                </p>
                <button
                  type="button"
                  className="text-sm font-medium text-zinc-900 underline-offset-4 hover:underline dark:text-zinc-50"
                  onClick={() => {
                    retryDocumentsLoad();
                  }}
                >
                  Retry
                </button>
              </div>
            ) : null}

            {documentsView.kind === "ready" &&
            documentsView.documents.length === 0 ? (
              <p
                className="text-sm text-zinc-600 dark:text-zinc-400"
                role="status"
              >
                No documents in this collection yet.
              </p>
            ) : null}

            {documentsView.kind === "ready" &&
            documentsView.documents.length > 0 ? (
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
                      <th scope="col" className="px-4 py-2 font-medium">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                    {documentsView.documents.map((document) => {
                      const processLabel = processActionLabel(document.status);
                      const indexLabel = indexActionLabel(document.status);
                      const processFeedback =
                        processFeedbackByDocumentId[document.id] ?? {
                          kind: "idle" as const,
                        };
                      const indexFeedback =
                        indexFeedbackByDocumentId[document.id] ?? {
                          kind: "idle" as const,
                        };
                      const rowActionState = {
                        status: document.status,
                        processFeedbackKind: processFeedback.kind,
                        indexFeedbackKind: indexFeedback.kind,
                        documentsReady: documentsView.kind === "ready",
                      };
                      const disableProcess =
                        shouldDisableProcessButton(rowActionState);
                      const disableIndex =
                        shouldDisableIndexButton(rowActionState);

                      return (
                      <tr key={document.id}>
                        <td className="px-4 py-3 font-medium text-zinc-900 dark:text-zinc-50">
                          {document.original_filename}
                        </td>
                        <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">
                          {formatFileSize(document.size_bytes)}
                        </td>
                        <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">
                          {formatDocumentStatus(document.status)}
                          {document.status === "PROCESSED" ? (
                            <span className="mt-0.5 block text-xs text-zinc-500 dark:text-zinc-500">
                              Text chunks stored; vectors not indexed yet
                            </span>
                          ) : null}
                        </td>
                        <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">
                          {formatTimestamp(document.created_at)}
                        </td>
                        <td className="px-4 py-3 align-top">
                          <div className="flex min-w-[8rem] flex-col gap-1.5">
                            {processLabel ? (
                              <button
                                type="button"
                                className={`${authButtonClassName} w-full px-3 py-1.5 text-xs sm:w-auto`}
                                disabled={disableProcess}
                                aria-busy={processFeedback.kind === "loading"}
                                onClick={() => {
                                  void runProcessDocument(document.id);
                                }}
                              >
                                {processFeedback.kind === "loading"
                                  ? "Processing…"
                                  : processLabel}
                              </button>
                            ) : document.status === "PROCESSING" ? (
                              <span
                                className="text-xs text-zinc-600 dark:text-zinc-400"
                                role="status"
                              >
                                Processing…
                              </span>
                            ) : null}
                            {indexLabel ? (
                              <button
                                type="button"
                                className={`${authButtonClassName} w-full px-3 py-1.5 text-xs sm:w-auto`}
                                disabled={disableIndex}
                                aria-busy={indexFeedback.kind === "loading"}
                                onClick={() => {
                                  void runIndexDocument(document.id);
                                }}
                              >
                                {indexFeedback.kind === "loading"
                                  ? "Indexing…"
                                  : indexLabel}
                              </button>
                            ) : document.status === "INDEXING" ? (
                              <span
                                className="text-xs text-zinc-600 dark:text-zinc-400"
                                role="status"
                              >
                                Indexing…
                              </span>
                            ) : document.status === "READY" ? (
                              <span className="text-xs text-zinc-500 dark:text-zinc-500">
                                Indexed (reprocess unavailable)
                              </span>
                            ) : null}
                            {processFeedback.kind === "success" ? (
                              <p
                                className="text-xs text-green-700 dark:text-green-400"
                                role="status"
                              >
                                {processFeedback.chunkCount} chunk
                                {processFeedback.chunkCount === 1 ? "" : "s"}{" "}
                                from latest process run
                              </p>
                            ) : null}
                            {indexFeedback.kind === "success" ? (
                              <p
                                className="text-xs text-green-700 dark:text-green-400"
                                role="status"
                              >
                                {indexFeedback.embeddedChunkCount} embedding
                                {indexFeedback.embeddedChunkCount === 1
                                  ? ""
                                  : "s"}{" "}
                                ({indexFeedback.embeddingModel}) from latest
                                index run
                              </p>
                            ) : null}
                            {processFeedback.kind === "error" ? (
                              <p
                                className="text-xs text-red-600 dark:text-red-400"
                                role="alert"
                              >
                                {processFeedback.message}
                              </p>
                            ) : null}
                            {indexFeedback.kind === "error" ? (
                              <p
                                className="text-xs text-red-600 dark:text-red-400"
                                role="alert"
                              >
                                {indexFeedback.message}
                              </p>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                      );
                    })}
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
