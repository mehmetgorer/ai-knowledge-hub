"use server";

import { redirect } from "next/navigation";

import { getNeonAuth } from "@/lib/auth/server";

export async function signOut(): Promise<void> {
  const auth = getNeonAuth();
  if (!auth) {
    redirect("/auth/sign-in");
  }

  const { error } = await auth.signOut();
  if (error) {
    redirect("/auth/sign-in");
  }

  redirect("/");
}
