"use server";

import { redirect } from "next/navigation";

import { AUTH_CONFIGURATION_ERROR } from "@/lib/auth/config";
import { getNeonAuth } from "@/lib/auth/server";

import type { AuthFormState } from "../sign-up/actions";

export async function signInWithEmail(
  _prevState: AuthFormState,
  formData: FormData,
): Promise<AuthFormState> {
  const auth = getNeonAuth();
  if (!auth) {
    return { error: AUTH_CONFIGURATION_ERROR };
  }

  const email = formData.get("email");
  const password = formData.get("password");
  if (typeof email !== "string" || !email.trim()) {
    return { error: "Email address is required." };
  }
  if (typeof password !== "string" || !password) {
    return { error: "Password is required." };
  }

  const { error } = await auth.signIn.email({
    email: email.trim(),
    password,
  });

  if (error) {
    return { error: error.message || "Failed to sign in. Try again." };
  }

  redirect("/dashboard");
}
