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

// A reconciliation batch can take 60-180s+ (real per-exception LLM
// investigation calls), and this proxy holds the connection open for the
// full duration of the upstream request. Vercel's default serverless
// function timeout (10s on Hobby without Fluid Compute) kills the proxy's
// connection well before that completes — the Render backend keeps working
// and the batch genuinely finishes, but the browser never gets a response,
// so the UI is stuck showing "Reconciling..." forever even though the data
// already landed. This raises the ceiling so long-running requests can
// actually complete end-to-end.
export const maxDuration = 300;

const BACKEND_URL = process.env.VERIDEX_BACKEND_URL || "http://127.0.0.1:8000";
const BACKEND_API_KEY =
  process.env.VERIDEX_API_KEY || process.env.SENTINEL_API_KEY || "";

// Paths that must never be reachable through the public proxy: the Razorpay
// webhook receivers authenticate with their own HMAC (the proxy would only
// ever add noise there), and the interactive API docs / schema are not part
// of the UI.
const BLOCKED_PREFIXES = ["api/v1/webhooks", "docs", "redoc", "openapi.json"];

function isForwardable(path: string[]): boolean {
  if (path.some((seg) => seg === ".." || seg === "." || seg.includes("\\"))) return false;
  const joined = path.join("/").toLowerCase();
  return !BLOCKED_PREFIXES.some((p) => joined === p || joined.startsWith(p + "/"));
}

async function forward(req: NextRequest, path: string[]): Promise<NextResponse> {
  if (!isForwardable(path)) {
    return NextResponse.json({ detail: "Not found.", status_code: 404 }, { status: 404 });
  }
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
    // Do not echo the error text back: it can contain the internal backend URL.
    console.error("Proxy upstream error:", err);
    return NextResponse.json(
      {
        detail: "Backend unreachable through proxy.",
        status_code: 502,
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
