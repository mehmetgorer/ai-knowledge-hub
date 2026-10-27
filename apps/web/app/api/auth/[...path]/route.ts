import { getNeonAuth } from "@/lib/auth/server";
import { authNotConfiguredResponse } from "@/lib/auth/http";

const auth = getNeonAuth();
const handler = auth?.handler();

export async function GET(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  if (!handler) {
    return authNotConfiguredResponse();
  }
  return handler.GET(request, context);
}

export async function POST(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  if (!handler) {
    return authNotConfiguredResponse();
  }
  return handler.POST(request, context);
}
