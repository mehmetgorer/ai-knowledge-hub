const MIN_COOKIE_SECRET_LENGTH = 32;

export const AUTH_CONFIGURATION_ERROR =
  "Authentication is not configured. Set NEON_AUTH_BASE_URL and NEON_AUTH_COOKIE_SECRET in apps/web/.env.local (see .env.example).";

export type NeonAuthEnvConfig = {
  baseUrl: string;
  cookies: {
    secret: string;
  };
};

/**
 * Read Neon Auth settings from the environment. Returns null when required values
 * are missing or invalid so the app can fail closed without inventing credentials.
 */
export function readNeonAuthConfig(): NeonAuthEnvConfig | null {
  const baseUrl = process.env.NEON_AUTH_BASE_URL?.trim();
  const secret = process.env.NEON_AUTH_COOKIE_SECRET?.trim();

  if (!baseUrl || !secret) {
    return null;
  }

  if (secret.length < MIN_COOKIE_SECRET_LENGTH) {
    return null;
  }

  return {
    baseUrl,
    cookies: { secret },
  };
}

export function isNeonAuthConfigured(): boolean {
  return readNeonAuthConfig() !== null;
}
