"use client";

import { useActionState } from "react";

import {
  AuthShell,
  authButtonClassName,
  authFieldClassName,
  authLabelClassName,
} from "@/components/auth-shell";

import { signInWithEmail } from "./actions";

export default function SignInPage() {
  const [state, formAction, isPending] = useActionState(signInWithEmail, null);

  return (
    <AuthShell
      title="Sign in"
      alternateHref="/auth/sign-up"
      alternateLabel="Need an account? Sign up"
    >
      <form action={formAction} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="email" className={authLabelClassName}>
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="email"
            className={authFieldClassName}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="password" className={authLabelClassName}>
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
            className={authFieldClassName}
          />
        </div>
        {state?.error ? (
          <p className="text-sm text-red-600 dark:text-red-400" role="alert">
            {state.error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={isPending}
          className={authButtonClassName}
        >
          {isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </AuthShell>
  );
}
