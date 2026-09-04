/**
 * Centralized HTTP API Client for Veridex Frontend.
 * Communicates strictly with the running FastAPI backend.
 */

// By default, requests go through the same-origin `/api/proxy` route
// (frontend/app/api/proxy/[...path]/route.ts), which attaches the backend's
// API key server-side. The key must never live in browser-shipped code: any
// `NEXT_PUBLIC_*` var is baked into the client bundle and readable via
// view-source, which would defeat the access-control gate entirely. Setting
// NEXT_PUBLIC_API_BASE_URL opts back into calling the backend directly (e.g.
// local dev without auth configured) — no API key is ever attached from the
// browser in either mode.
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/proxy";

export class ApiError extends Error {
  statusCode: number;
  data: unknown;

  constructor(message: string, statusCode: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.data = data;
  }
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const url = endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorMessage = `API request failed with status ${response.status}`;
      let errorData: unknown = null;
      try {
        errorData = await response.json();
        if (errorData && typeof errorData === "object") {
          const detail = (errorData as Record<string, unknown>).detail;
          if (typeof detail === "string") {
            errorMessage = detail;
          } else if (Array.isArray(detail)) {
            errorMessage = detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join("; ");
          }
        }
      } catch {
        // Fall back to status text
        errorMessage = response.statusText || errorMessage;
      }
      throw new ApiError(errorMessage, response.status, errorData);
    }

    return (await response.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : "Network error occurred connecting to backend";
    throw new ApiError(message, 0);
  }
}
