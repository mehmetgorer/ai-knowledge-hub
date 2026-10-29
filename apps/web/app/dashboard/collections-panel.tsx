"use client";

import { useCallback, useEffect, useId, useState } from "react";

import {
  authButtonClassName,
  authFieldClassName,
  authLabelClassName,
} from "@/components/auth-shell";
import {
  createCollection,
  fetchCollections,
  validateCollectionNameInput,
  type CollectionRecord,
} from "@/lib/api/client";

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; collections: CollectionRecord[] }
  | { kind: "error"; message: string };

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString();
}

export function CollectionsPanel() {
  const nameFieldId = useId();
  const [loadState, setLoadState] = useState<LoadState>({ kind: "loading" });
  const [nameInput, setNameInput] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadCollections = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoadState({ kind: "loading" });
    }
    const result = await fetchCollections();
    if (!result.ok) {
      setLoadState({ kind: "error", message: result.error.message });
      return;
    }
    setLoadState({ kind: "ready", collections: result.collections });
  }, []);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const result = await fetchCollections();
      if (cancelled) {
        return;
      }
      if (!result.ok) {
        setLoadState({ kind: "error", message: result.error.message });
        return;
      }
      setLoadState({ kind: "ready", collections: result.collections });
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setFormError(null);
    const validated = validateCollectionNameInput(nameInput);
    if (!validated) {
      setFormError("Enter a non-empty name (max 255 characters).");
      return;
    }

    setIsSubmitting(true);
    const result = await createCollection(validated);
    setIsSubmitting(false);

    if (!result.ok) {
      setFormError(result.error.message);
      return;
    }

    setNameInput("");
    await loadCollections({ silent: true });
  }

  return (
    <section
      className="mt-8 space-y-6 rounded-lg border border-zinc-200 p-6 dark:border-zinc-800"
      aria-labelledby="collections-heading"
    >
      <div>
        <h2
          id="collections-heading"
          className="text-lg font-medium text-zinc-900 dark:text-zinc-50"
        >
          Collections
        </h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Your knowledge bases, stored in the API and scoped to your account.
        </p>
      </div>

      <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={handleCreate}>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <label htmlFor={nameFieldId} className={authLabelClassName}>
            New collection name
          </label>
          <input
            id={nameFieldId}
            name="name"
            type="text"
            required
            maxLength={255}
            autoComplete="off"
            disabled={isSubmitting || loadState.kind === "loading"}
            value={nameInput}
            onChange={(event) => {
              setNameInput(event.target.value);
              setFormError(null);
            }}
            className={authFieldClassName}
            placeholder="Research notes"
          />
        </div>
        <button
          type="submit"
          disabled={isSubmitting || loadState.kind === "loading"}
          className={`${authButtonClassName} sm:w-auto sm:min-w-[9rem]`}
        >
          {isSubmitting ? "Creating…" : "Create"}
        </button>
      </form>

      {formError ? (
        <p className="text-sm text-red-600 dark:text-red-400" role="alert">
          {formError}
        </p>
      ) : null}

      {loadState.kind === "loading" ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400" role="status">
          Loading collections…
        </p>
      ) : null}

      {loadState.kind === "error" ? (
        <div className="space-y-3">
          <p className="text-sm text-red-600 dark:text-red-400" role="alert">
            {loadState.message}
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

      {loadState.kind === "ready" && loadState.collections.length === 0 ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400" role="status">
          No collections yet. Create one above to get started.
        </p>
      ) : null}

      {loadState.kind === "ready" && loadState.collections.length > 0 ? (
        <ul className="divide-y divide-zinc-200 rounded-md border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
          {loadState.collections.map((collection) => (
            <li
              key={collection.id}
              className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="font-medium text-zinc-900 dark:text-zinc-50">
                  {collection.name}
                </p>
                <p className="mt-0.5 font-mono text-xs text-zinc-500 dark:text-zinc-400">
                  {collection.id}
                </p>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Updated {formatTimestamp(collection.updated_at)}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
