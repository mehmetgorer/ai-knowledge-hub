import Link from "next/link";
import type { ReactNode } from "react";

type AuthShellProps = {
  title: string;
  children: ReactNode;
  alternateHref: string;
  alternateLabel: string;
};

export function AuthShell({
  title,
  children,
  alternateHref,
  alternateLabel,
}: AuthShellProps) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-center text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          {title}
        </h1>
        {children}
        <p className="text-center text-sm text-zinc-600 dark:text-zinc-400">
          <Link
            href={alternateHref}
            className="font-medium text-zinc-900 underline-offset-4 hover:underline dark:text-zinc-50"
          >
            {alternateLabel}
          </Link>
        </p>
      </div>
    </main>
  );
}

export const authFieldClassName =
  "block w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-500";

export const authLabelClassName =
  "block text-sm font-medium text-zinc-700 dark:text-zinc-300";

export const authButtonClassName =
  "flex w-full justify-center rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200";
