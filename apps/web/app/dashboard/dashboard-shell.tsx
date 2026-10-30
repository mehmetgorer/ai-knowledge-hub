"use client";

import { useCallback, useEffect, useId, useState } from "react";

import { DashboardAppHeader } from "@/components/dashboard/app-header";
import {
  dashboardTabClassName,
} from "@/components/dashboard/ui";
import { fetchCollections } from "@/lib/api/client";

import {
  CollectionSidebar,
  type CollectionsLoadState,
} from "./collection-sidebar";
import { CollectionWorkspace, type WorkspaceTab } from "./documents-panel";
import { MobileCollectionNav } from "./mobile-collection-nav";
import { VerifyPythonApi } from "./verify-python-api";

type DashboardShellProps = {
  userLabel: string;
  sessionUserId: string;
};

const WORKSPACE_TABS: {
  id: WorkspaceTab;
  label: string;
  shortLabel: string;
}[] = [
  { id: "ask", label: "Ask AI", shortLabel: "Ask" },
  { id: "search", label: "Semantic Search", shortLabel: "Search" },
  { id: "documents", label: "Documents", shortLabel: "Docs" },
];

export function DashboardShell(props: DashboardShellProps) {
  const tabListId = useId();
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

  const collectionNavProps = {
    loadState: collectionsState,
    selectedCollectionId,
    onSelectCollection: setSelectedCollectionId,
    onReloadCollections: loadCollections,
    nameInput: collectionNameInput,
    onNameInputChange: setCollectionNameInput,
    formError: collectionFormError,
    onFormErrorChange: setCollectionFormError,
    isCreating: isCreatingCollection,
    onCreatingChange: setIsCreatingCollection,
  };

  return (
    <div className="flex min-h-dvh flex-col bg-zinc-50/80 dark:bg-zinc-950">
      <DashboardAppHeader userLabel={props.userLabel} />

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <CollectionSidebar {...collectionNavProps} />

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="shrink-0 border-b border-zinc-200/80 bg-white/70 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-950/50 sm:px-5">
            <nav
              className="grid w-full grid-cols-3 gap-1 rounded-lg border border-zinc-200/80 bg-zinc-100/90 p-1 dark:border-zinc-800 dark:bg-zinc-900/60 lg:inline-grid lg:max-w-xl"
              role="tablist"
              aria-label="Workspace views"
              id={tabListId}
            >
              {WORKSPACE_TABS.map((tab) => {
                const selected = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    id={`${tabListId}-tab-${tab.id}`}
                    aria-selected={selected}
                    aria-controls={`${tabListId}-panel-${tab.id}`}
                    tabIndex={selected ? 0 : -1}
                    className={`${dashboardTabClassName(selected)} min-w-0 truncate px-2 py-2 text-center sm:px-3`}
                    onClick={() => {
                      setActiveTab(tab.id);
                    }}
                  >
                    <span className="sm:hidden">{tab.shortLabel}</span>
                    <span className="hidden sm:inline">{tab.label}</span>
                  </button>
                );
              })}
            </nav>

            <div className="mt-2 lg:hidden">
              <MobileCollectionNav {...collectionNavProps} />
            </div>
          </div>

          <main className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-3 py-4 sm:px-5 sm:py-5">
            <CollectionWorkspace
              selectedCollectionId={selectedCollectionId}
              collectionsState={collectionsState}
              activeTab={activeTab}
              onReloadCollections={loadCollections}
              tabListId={tabListId}
            />
          </main>

          <footer className="shrink-0 border-t border-zinc-200/80 bg-zinc-50/50 px-3 py-3 dark:border-zinc-800 dark:bg-zinc-950/60 sm:px-5">
            <details className="group max-w-3xl">
              <summary className="cursor-pointer list-none text-xs font-medium uppercase tracking-wide text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/40 dark:text-zinc-400 [&::-webkit-details-marker]:hidden">
                Developer diagnostics
              </summary>
              <div className="mt-2">
                <VerifyPythonApi sessionUserId={props.sessionUserId} compact />
              </div>
            </details>
          </footer>
        </div>
      </div>
    </div>
  );
}
