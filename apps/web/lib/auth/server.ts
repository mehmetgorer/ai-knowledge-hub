import { createNeonAuth } from "@neondatabase/auth/next/server";

import { readNeonAuthConfig } from "./config";

type NeonAuthInstance = ReturnType<typeof createNeonAuth>;

let cachedAuth: NeonAuthInstance | null | undefined;

/**
 * Lazily create the Neon Auth server instance when configuration is present.
 * Returns null when auth env vars are missing (CI builds, local without Neon).
 */
export function getNeonAuth(): NeonAuthInstance | null {
  if (cachedAuth !== undefined) {
    return cachedAuth;
  }

  const config = readNeonAuthConfig();
  if (!config) {
    cachedAuth = null;
    return null;
  }

  cachedAuth = createNeonAuth({
    baseUrl: config.baseUrl,
    cookies: config.cookies,
  });
  return cachedAuth;
}
