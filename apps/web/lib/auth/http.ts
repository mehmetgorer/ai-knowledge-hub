import { NextResponse } from "next/server";

import { AUTH_CONFIGURATION_ERROR } from "./config";

export function authNotConfiguredResponse(): Response {
  return NextResponse.json(
    { error: AUTH_CONFIGURATION_ERROR },
    { status: 503 },
  );
}
