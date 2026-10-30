/** Shared dashboard surface classes (Geist + violet accent, dark-first). */

export const dashboardFieldClassName =
  "block w-full rounded-lg border border-zinc-200/90 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 shadow-sm transition-colors focus:border-violet-500/70 focus:outline-none focus:ring-2 focus:ring-violet-500/20 dark:border-zinc-800 dark:bg-zinc-950/80 dark:text-zinc-50 dark:placeholder:text-zinc-500 dark:focus:border-violet-400/60 dark:focus:ring-violet-400/15";

export const dashboardLabelClassName =
  "block text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400";

export const dashboardPrimaryButtonClassName =
  "inline-flex items-center justify-center rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-violet-600 dark:hover:bg-violet-500";

export const dashboardSecondaryButtonClassName =
  "inline-flex items-center justify-center rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-800 shadow-sm transition-colors hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800/80";

export const dashboardGhostButtonClassName =
  "inline-flex items-center justify-center rounded-lg px-3 py-1.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 disabled:cursor-not-allowed disabled:opacity-50 dark:text-zinc-400 dark:hover:bg-zinc-800/80 dark:hover:text-zinc-50";

export const dashboardPanelClassName =
  "rounded-xl border border-zinc-200/80 bg-white shadow-sm dark:border-zinc-800/90 dark:bg-zinc-950/50";

export const dashboardMutedTextClassName =
  "text-sm text-zinc-600 dark:text-zinc-400";

export function dashboardTabClassName(active: boolean): string {
  const base =
    "relative rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/40";
  if (active) {
    return `${base} bg-violet-600/10 text-violet-900 dark:bg-violet-500/15 dark:text-violet-100`;
  }
  return `${base} text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100`;
}

export function documentStatusBadgeClassName(status: string): string {
  const base =
    "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset";
  switch (status) {
    case "READY":
      return `${base} bg-emerald-500/10 text-emerald-800 ring-emerald-500/20 dark:text-emerald-300`;
    case "PROCESSED":
      return `${base} bg-sky-500/10 text-sky-800 ring-sky-500/20 dark:text-sky-300`;
    case "PROCESSING":
    case "INDEXING":
      return `${base} bg-amber-500/10 text-amber-900 ring-amber-500/20 dark:text-amber-200`;
    case "FAILED":
      return `${base} bg-red-500/10 text-red-800 ring-red-500/20 dark:text-red-300`;
    default:
      return `${base} bg-zinc-500/10 text-zinc-700 ring-zinc-500/15 dark:text-zinc-300`;
  }
}
