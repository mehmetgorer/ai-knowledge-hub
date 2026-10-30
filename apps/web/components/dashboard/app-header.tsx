import Link from "next/link";

import { SignOutButton } from "@/app/dashboard/sign-out-button";

type DashboardAppHeaderProps = {
  userLabel: string;
};

export function DashboardAppHeader(props: DashboardAppHeaderProps) {
  return (
    <header className="shrink-0 border-b border-zinc-200/80 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
        <Link
          href="/"
          className="min-w-0 truncate text-sm font-semibold tracking-tight text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/40 dark:text-zinc-50"
        >
          AI Knowledge Hub
        </Link>
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <span
            className="hidden max-w-[10rem] truncate text-xs text-zinc-500 sm:inline sm:max-w-xs sm:text-sm dark:text-zinc-400"
            title={props.userLabel}
          >
            {props.userLabel}
          </span>
          <SignOutButton variant="ghost" />
        </div>
      </div>
    </header>
  );
}
