/**
 * Server-side proxy to the VERIDEX FastAPI backend.
 *
 * The backend's access-control key must never reach the browser: any
 * `NEXT_PUBLIC_*` env var is baked into the client-side JS bundle and is
 * readable by anyone via view-source on a deployed instance, which defeats
 * the point of an API key entirely. This route runs only on the Next.js
 * server, reads the key from a server-only env var (no `NEXT_PUBLIC_`
 * prefix), and attaches it to the outbound request itself — the browser
 * only ever talks to this same-origin proxy and never sees the key.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.VERIDEX_BACKEND_URL || "http://127.0.0.1:8000";
const BACKEND_API_KEY =
  process.env.VERIDEX_API_KEY || process.env.SENTINEL_API_KEY || "";

async function forward(req: NextRequest, path: string[]): Promise<NextResponse> {
  const targetUrl = `${BACKEND_URL}/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (BACKEND_API_KEY) headers.set("x-api-key", BACKEND_API_KEY);

  const hasBody = !["GET", "HEAD"].includes(req.method);
  const body = hasBody ? await req.arrayBuffer() : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body: body && body.byteLength > 0 ? body : undefined,
      cache: "no-store",
    });
  } catch (err) {
    return NextResponse.json(
      {
        detail: "Backend unreachable through proxy.",
        status_code: 502,
        error: err instanceof Error ? err.message : String(err),
      },
      { status: 502 }
    );
  }

  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  if (upstreamContentType) responseHeaders.set("content-type", upstreamContentType);

  const buf = await upstream.arrayBuffer();
  return new NextResponse(buf, { status: upstream.status, headers: responseHeaders });
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).path);
}
