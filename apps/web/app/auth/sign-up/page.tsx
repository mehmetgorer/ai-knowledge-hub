"use client";

import { useActionState } from "react";

import {
  AuthShell,
  authButtonClassName,
  authFieldClassName,
  authLabelClassName,
} from "@/components/auth-shell";

import { signUpWithEmail } from "./actions";

export default function SignUpPage() {
  const [state, formAction, isPending] = useActionState(signUpWithEmail, null);

  return (
    <AuthShell
      title="Create account"
      alternateHref="/auth/sign-in"
      alternateLabel="Already have an account? Sign in"
    >
      <form action={formAction} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="name" className={authLabelClassName}>
            Name
          </label>
          <input
            id="name"
            name="name"
            type="text"
            required
            autoComplete="name"
            className={authFieldClassName}
          />
        </div>
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
            autoComplete="new-password"
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
          {isPending ? "Creating account…" : "Sign up"}
        </button>
      </form>
    </AuthShell>
  );
}
