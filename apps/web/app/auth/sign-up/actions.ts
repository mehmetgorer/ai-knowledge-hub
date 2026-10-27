"use server";

import { redirect } from "next/navigation";

import { AUTH_CONFIGURATION_ERROR } from "@/lib/auth/config";
import { getNeonAuth } from "@/lib/auth/server";

export type AuthFormState = { error: string } | null;

export async function signUpWithEmail(
  _prevState: AuthFormState,
  formData: FormData,
): Promise<AuthFormState> {
  const auth = getNeonAuth();
  if (!auth) {
    return { error: AUTH_CONFIGURATION_ERROR };
  }

  const email = formData.get("email");
  if (typeof email !== "string" || !email.trim()) {
    return { error: "Email address is required." };
  }

  const name = formData.get("name");
  const password = formData.get("password");
  if (typeof name !== "string" || !name.trim()) {
    return { error: "Name is required." };
  }
  if (typeof password !== "string" || !password) {
    return { error: "Password is required." };
  }

  const { error } = await auth.signUp.email({
    email: email.trim(),
    name: name.trim(),
    password,
  });

  if (error) {
    return { error: error.message || "Failed to create account." };
  }

  redirect("/dashboard");
}
