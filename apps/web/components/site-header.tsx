import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="border-b border-zinc-200/80 bg-white/90 dark:border-zinc-800 dark:bg-zinc-950/90">
      <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-50"
        >
          AI Knowledge Hub
        </Link>
        <nav className="flex items-center gap-3 text-sm">
          <Link
            href="/auth/sign-in"
            className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
          >
            Sign in
          </Link>
          <Link
            href="/dashboard"
            className="rounded-md bg-violet-600/10 px-2.5 py-1 font-medium text-violet-800 dark:bg-violet-500/15 dark:text-violet-200"
          >
            Dashboard
          </Link>
        </nav>
      </div>
    </header>
  );
}
