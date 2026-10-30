"use client";

import { useId } from "react";

import {
  dashboardFieldClassName,
  dashboardGhostButtonClassName,
  dashboardLabelClassName,
  dashboardMutedTextClassName,
  dashboardSecondaryButtonClassName,
} from "@/components/dashboard/ui";
import {
  createCollection,
  validateCollectionNameInput,
  type CollectionRecord,
} from "@/lib/api/client";

export type CollectionsLoadState =
  | { kind: "loading" }
  | { kind: "ready"; collections: CollectionRecord[] }
  | { kind: "error"; message: string };

type CollectionSidebarProps = {
  loadState: CollectionsLoadState;
  selectedCollectionId: string;
  onSelectCollection: (collectionId: string) => void;
  onReloadCollections: (options?: { silent?: boolean }) => Promise<void>;
  nameInput: string;
  onNameInputChange: (value: string) => void;
  formError: string | null;
  onFormErrorChange: (message: string | null) => void;
  isCreating: boolean;
  onCreatingChange: (creating: boolean) => void;
};

export function CollectionSidebar(props: CollectionSidebarProps) {
  const nameFieldId = useId();

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (props.isCreating) {
      return;
    }

    props.onFormErrorChange(null);
    const validated = validateCollectionNameInput(props.nameInput);
    if (!validated) {
      props.onFormErrorChange("Enter a non-empty name (max 255 characters).");
      return;
    }

    props.onCreatingChange(true);
    const result = await createCollection(validated);
    props.onCreatingChange(false);

    if (!result.ok) {
      props.onFormErrorChange(result.error.message);
      return;
    }

    props.onNameInputChange("");
    await props.onReloadCollections({ silent: true });
  }

  return (
    <aside
      className="flex h-full min-h-0 flex-col border-b border-zinc-200/80 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-950/40 lg:w-72 lg:shrink-0 lg:border-b-0 lg:border-r"
      aria-label="Collections"
    >
      <div className="border-b border-zinc-200/80 px-4 py-4 dark:border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          Collections
        </h2>
        <p className={`mt-1 ${dashboardMutedTextClassName} text-xs`}>
          Knowledge bases scoped to your account.
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <form className="space-y-2" onSubmit={handleCreate}>
          <label htmlFor={nameFieldId} className={dashboardLabelClassName}>
            New collection
          </label>
          <input
            id={nameFieldId}
            name="name"
            type="text"
            required
            maxLength={255}
            autoComplete="off"
            disabled={
              props.isCreating || props.loadState.kind === "loading"
            }
            value={props.nameInput}
            onChange={(event) => {
              props.onNameInputChange(event.target.value);
              props.onFormErrorChange(null);
            }}
            className={dashboardFieldClassName}
            placeholder="Research notes"
          />
          <button
            type="submit"
            disabled={
              props.isCreating || props.loadState.kind === "loading"
            }
            className={`${dashboardSecondaryButtonClassName} w-full`}
          >
            {props.isCreating ? "Creating…" : "Create collection"}
          </button>
          {props.formError ? (
            <p className="text-xs text-red-600 dark:text-red-400" role="alert">
              {props.formError}
            </p>
          ) : null}
        </form>

        {props.loadState.kind === "loading" ? (
          <p className={dashboardMutedTextClassName} role="status">
            Loading…
          </p>
        ) : null}

        {props.loadState.kind === "error" ? (
          <div className="space-y-2">
            <p className="text-sm text-red-600 dark:text-red-400" role="alert">
              {props.loadState.message}
            </p>
            <button
              type="button"
              className={dashboardGhostButtonClassName}
              onClick={() => {
                void props.onReloadCollections();
              }}
            >
              Retry
            </button>
          </div>
        ) : null}

        {props.loadState.kind === "ready" &&
        props.loadState.collections.length === 0 ? (
          <p className={`${dashboardMutedTextClassName} text-xs`} role="status">
            Create a collection to start uploading documents.
          </p>
        ) : null}

        {props.loadState.kind === "ready" &&
        props.loadState.collections.length > 0 ? (
          <nav aria-label="Collection list">
            <ul className="space-y-1">
              {props.loadState.collections.map((collection) => {
                const active = collection.id === props.selectedCollectionId;
                return (
                  <li key={collection.id}>
                    <button
                      type="button"
                      onClick={() => {
                        props.onSelectCollection(collection.id);
                      }}
                      className={`w-full rounded-lg border px-3 py-2.5 text-left text-sm transition-colors ${
                        active
                          ? "border-violet-500/40 bg-violet-600/10 text-violet-950 dark:border-violet-400/30 dark:bg-violet-500/10 dark:text-violet-100"
                          : "border-transparent text-zinc-800 hover:border-zinc-200 hover:bg-white dark:text-zinc-200 dark:hover:border-zinc-800 dark:hover:bg-zinc-900/60"
                      }`}
                      aria-current={active ? "true" : undefined}
                    >
                      <span className="font-medium">{collection.name}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
        ) : null}
      </div>
    </aside>
  );
}
