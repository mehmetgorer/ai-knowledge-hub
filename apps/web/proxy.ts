import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { getNeonAuth } from "@/lib/auth/server";

const SIGN_IN_PATH = "/auth/sign-in";

export default async function proxy(request: NextRequest) {
  const auth = getNeonAuth();
  if (!auth) {
    return NextResponse.redirect(new URL(SIGN_IN_PATH, request.url));
  }

  return auth.middleware({
    loginUrl: SIGN_IN_PATH,
  })(request);
}

export const config = {
  matcher: ["/dashboard", "/dashboard/:path*"],
};
