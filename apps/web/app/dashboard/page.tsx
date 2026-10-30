import { connection } from "next/server";
import { redirect } from "next/navigation";

import { AUTH_CONFIGURATION_ERROR } from "@/lib/auth/config";
import { getNeonAuth } from "@/lib/auth/server";

import { DashboardShell } from "./dashboard-shell";

export const instant = false;

export default async function DashboardPage() {
  await connection();

  const auth = getNeonAuth();
  if (!auth) {
    return (
      <main className="mx-auto max-w-lg px-6 py-16">
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
  const userLabel = user.name ?? user.email ?? "Signed in";

  return (
    <DashboardShell
      userLabel={userLabel}
      sessionUserId={user.id ?? ""}
    />
  );
}
