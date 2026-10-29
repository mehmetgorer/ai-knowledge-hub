"use client";

import { useState } from "react";

import { authButtonClassName } from "@/components/auth-shell";
import { authedApiRequest } from "@/lib/api/client";

type VerifyResult =
  | { kind: "idle" }
  | { kind: "loading" }
  | {
      kind: "success";
      subject: string;
      matchesSessionUserId: boolean;
    }
  | { kind: "error"; message: string };

type VerifyPythonApiProps = {
  sessionUserId: string;
};

export function VerifyPythonApi({ sessionUserId }: VerifyPythonApiProps) {
  const [result, setResult] = useState<VerifyResult>({ kind: "idle" });

  async function handleVerify() {
    setResult({ kind: "loading" });

    const apiResult = await authedApiRequest("/auth/me", { method: "GET" });
    if (!apiResult.ok) {
      setResult({ kind: "error", message: apiResult.error.message });
      return;
    }

    let payload: unknown;
    try {
      payload = await apiResult.response.json();
    } catch {
      setResult({
        kind: "error",
        message: "Python API returned an invalid JSON response.",
      });
      return;
    }

    const subject =
      payload &&
      typeof payload === "object" &&
      "subject" in payload &&
      typeof (payload as { subject: unknown }).subject === "string"
        ? (payload as { subject: string }).subject
        : null;

    if (!subject) {
      setResult({
        kind: "error",
        message: "Python API did not return a verified subject.",
      });
      return;
    }

    const matchesSessionUserId = subject === sessionUserId;
    setResult({ kind: "success", subject, matchesSessionUserId });
  }

  return (
    <section className="mt-8 space-y-3 rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
      <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
        Verify Python API
      </h2>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Request a fresh JWT from Neon Auth and call{" "}
        <code className="text-xs">GET /auth/me</code> on the FastAPI service.
      </p>
      <button
        type="button"
        className={authButtonClassName}
        disabled={result.kind === "loading"}
        onClick={() => {
          void handleVerify();
        }}
      >
        {result.kind === "loading" ? "Verifying…" : "Verify Python API"}
      </button>
      {result.kind === "success" ? (
        <div className="space-y-1 text-sm" role="status">
          <p className="text-zinc-900 dark:text-zinc-50">
            Verified subject:{" "}
            <span className="font-mono">{result.subject}</span>
          </p>
          <p
            className={
              result.matchesSessionUserId
                ? "text-green-700 dark:text-green-400"
                : "text-red-600 dark:text-red-400"
            }
          >
            {result.matchesSessionUserId
              ? "Matches Neon session user ID: Yes"
              : "Subject mismatch: does not match your Neon session user ID."}
          </p>
        </div>
      ) : null}
      {result.kind === "error" ? (
        <p className="text-sm text-red-600 dark:text-red-400" role="alert">
          {result.message}
        </p>
      ) : null}
    </section>
  );
}
