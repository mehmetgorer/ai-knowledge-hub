"use client";

import { useCallback, useEffect, useState } from "react";

import {
  dashboardGhostButtonClassName,
  dashboardMutedTextClassName,
  dashboardTabClassName,
} from "@/components/dashboard/ui";
import { fetchCollections } from "@/lib/api/client";

import {
  CollectionSidebar,
  type CollectionsLoadState,
} from "./collection-sidebar";
import { CollectionWorkspace, type WorkspaceTab } from "./documents-panel";
import { SignOutButton } from "./sign-out-button";
import { VerifyPythonApi } from "./verify-python-api";

type DashboardShellProps = {
  userLabel: string;
  sessionUserId: string;
};

export function DashboardShell(props: DashboardShellProps) {
  const [collectionsState, setCollectionsState] = useState<CollectionsLoadState>(
    { kind: "loading" },
  );
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("ask");
  const [collectionNameInput, setCollectionNameInput] = useState("");
  const [collectionFormError, setCollectionFormError] = useState<string | null>(
    null,
  );
  const [isCreatingCollection, setIsCreatingCollection] = useState(false);

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

  const selectedCollectionName =
    collectionsState.kind === "ready"
      ? collectionsState.collections.find(
          (collection) => collection.id === selectedCollectionId,
        )?.name
      : undefined;

  return (
    <div className="flex min-h-[calc(100vh-3.25rem)] flex-col bg-zinc-50/80 dark:bg-zinc-950">
      <header className="border-b border-zinc-200/80 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wider text-violet-700 dark:text-violet-300">
              Workspace
            </p>
            <h1 className="truncate text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              AI Knowledge Hub
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <p
              className={`${dashboardMutedTextClassName} max-w-[14rem] truncate text-xs sm:max-w-xs sm:text-sm`}
              title={props.userLabel}
            >
              {props.userLabel}
            </p>
            <SignOutButton variant="ghost" />
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <CollectionSidebar
          loadState={collectionsState}
          selectedCollectionId={selectedCollectionId}
          onSelectCollection={setSelectedCollectionId}
          onReloadCollections={loadCollections}
          nameInput={collectionNameInput}
          onNameInputChange={setCollectionNameInput}
          formError={collectionFormError}
          onFormErrorChange={setCollectionFormError}
          isCreating={isCreatingCollection}
          onCreatingChange={setIsCreatingCollection}
        />

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="border-b border-zinc-200/80 bg-white/60 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950/40 sm:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div className="min-w-0">
                <p className={dashboardMutedTextClassName}>
                  Active collection
                </p>
                <p className="truncate text-base font-semibold text-zinc-900 dark:text-zinc-50">
                  {selectedCollectionName ?? "None selected"}
                </p>
              </div>
              <nav
                className="flex flex-wrap gap-1 rounded-xl border border-zinc-200/80 bg-zinc-100/80 p-1 dark:border-zinc-800 dark:bg-zinc-900/60"
                aria-label="Workspace views"
              >
                {(
                  [
                    ["ask", "Ask AI"],
                    ["search", "Semantic Search"],
                    ["documents", "Documents"],
                  ] as const
                ).map(([tab, label]) => (
                  <button
                    key={tab}
                    type="button"
                    className={dashboardTabClassName(activeTab === tab)}
                    aria-current={activeTab === tab ? "page" : undefined}
                    onClick={() => {
                      setActiveTab(tab);
                    }}
                  >
                    {label}
                  </button>
                ))}
              </nav>
            </div>
          </div>

          <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
            <CollectionWorkspace
              selectedCollectionId={selectedCollectionId}
              collectionsState={collectionsState}
              activeTab={activeTab}
              onReloadCollections={loadCollections}
            />
          </main>

          <footer className="border-t border-zinc-200/80 bg-zinc-50/50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950/60 sm:px-6">
            <details className="group max-w-3xl">
              <summary
                className={`${dashboardGhostButtonClassName} cursor-pointer list-none [&::-webkit-details-marker]:hidden`}
              >
                <span className="text-xs font-medium uppercase tracking-wide text-zinc-500 group-open:text-zinc-700 dark:text-zinc-400 dark:group-open:text-zinc-200">
                  Developer diagnostics
                </span>
              </summary>
              <div className="mt-3">
                <VerifyPythonApi sessionUserId={props.sessionUserId} compact />
              </div>
            </details>
          </footer>
        </div>
      </div>
    </div>
  );
}
