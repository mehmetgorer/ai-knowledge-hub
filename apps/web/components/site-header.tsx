import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-4">
        <Link
          href="/"
          className="text-sm font-semibold text-zinc-900 dark:text-zinc-50"
        >
          AI Knowledge Hub
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link
            href="/auth/sign-in"
            className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
          >
            Sign in
          </Link>
          <Link
            href="/dashboard"
            className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
          >
            Dashboard
          </Link>
        </nav>
      </div>
    </header>
  );
}
