import { connection } from "next/server";
import { redirect } from "next/navigation";

import { AUTH_CONFIGURATION_ERROR } from "@/lib/auth/config";
import { getNeonAuth } from "@/lib/auth/server";

import { SignOutButton } from "./sign-out-button";

export const instant = false;

export default async function DashboardPage() {
  await connection();

  const auth = getNeonAuth();
  if (!auth) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Dashboard
        </h1>
        <p className="mt-4 text-zinc-600 dark:text-zinc-400" role="alert">
          {AUTH_CONFIGURATION_ERROR}
        </p>
      </main>
    );
  }

  const { data: session } = await auth.getSession();
  if (!session?.user) {
    redirect("/auth/sign-in");
  }

  const user = session.user;

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
        Dashboard
      </h1>
      <p className="mt-2 text-zinc-600 dark:text-zinc-400">
        Signed in placeholder — API integration comes in a later phase.
      </p>
      <dl className="mt-8 space-y-4 rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
        <div>
          <dt className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            Name
          </dt>
          <dd className="mt-1 text-zinc-900 dark:text-zinc-50">
            {user.name ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            Email
          </dt>
          <dd className="mt-1 text-zinc-900 dark:text-zinc-50">
            {user.email ?? "—"}
          </dd>
        </div>
        {user.id ? (
          <div>
            <dt className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
              User ID
            </dt>
            <dd className="mt-1 font-mono text-sm text-zinc-900 dark:text-zinc-50">
              {user.id}
            </dd>
          </div>
        ) : null}
      </dl>
      <div className="mt-8 max-w-xs">
        <SignOutButton />
      </div>
    </main>
  );
}
