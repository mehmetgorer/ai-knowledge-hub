"use client";

import { useId } from "react";

import {
  dashboardFieldClassName,
  dashboardGhostButtonClassName,
  dashboardLabelClassName,
  dashboardMutedTextClassName,
} from "@/components/dashboard/ui";

import { CollectionCreateForm } from "./collection-create-form";
import type { CollectionsLoadState } from "./collection-sidebar";

type MobileCollectionNavProps = {
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

export function MobileCollectionNav(props: MobileCollectionNavProps) {
  const selectFieldId = useId();

  if (props.loadState.kind === "loading") {
    return (
      <p className={`${dashboardMutedTextClassName} text-xs`} role="status">
        Loading collections…
      </p>
    );
  }

  if (props.loadState.kind === "error") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs text-red-600 dark:text-red-400" role="alert">
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
    );
  }

  if (
    props.loadState.kind === "ready" &&
    props.loadState.collections.length === 0
  ) {
    return (
      <details className="rounded-lg border border-zinc-200/80 bg-white/80 dark:border-zinc-800 dark:bg-zinc-950/50">
        <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-zinc-800 dark:text-zinc-100">
          New collection
        </summary>
        <div className="border-t border-zinc-200 px-3 py-3 dark:border-zinc-800">
          <CollectionCreateForm
            nameInput={props.nameInput}
            onNameInputChange={props.onNameInputChange}
            formError={props.formError}
            onFormErrorChange={props.onFormErrorChange}
            isCreating={props.isCreating}
            onCreatingChange={props.onCreatingChange}
            onReloadCollections={props.onReloadCollections}
            disabled={props.isCreating}
            submitLabel="Create"
          />
        </div>
      </details>
    );
  }

  if (props.loadState.kind !== "ready") {
    return null;
  }

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="min-w-0">
        <label htmlFor={selectFieldId} className={dashboardLabelClassName}>
          Collection
        </label>
        <select
          id={selectFieldId}
          value={props.selectedCollectionId}
          disabled={props.loadState.collections.length === 0}
          onChange={(event) => {
            props.onSelectCollection(event.target.value);
          }}
          className={dashboardFieldClassName}
        >
          {props.loadState.collections.map((collection) => (
            <option key={collection.id} value={collection.id}>
              {collection.name}
            </option>
          ))}
        </select>
      </div>
      <details className="rounded-lg border border-zinc-200/80 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-900/40">
        <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-zinc-600 dark:text-zinc-300">
          New collection
        </summary>
        <div className="border-t border-zinc-200 px-3 py-3 dark:border-zinc-800">
          <CollectionCreateForm
            nameInput={props.nameInput}
            onNameInputChange={props.onNameInputChange}
            formError={props.formError}
            onFormErrorChange={props.onFormErrorChange}
            isCreating={props.isCreating}
            onCreatingChange={props.onCreatingChange}
            onReloadCollections={props.onReloadCollections}
            disabled={props.isCreating}
            submitLabel="Create"
          />
        </div>
      </details>
    </div>
  );
}
