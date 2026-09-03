/**
 * Centralized HTTP API Client for Veridex Frontend.
 * Communicates strictly with the running FastAPI backend.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const API_KEY = process.env.NEXT_PUBLIC_VERIDEX_API_KEY || process.env.NEXT_PUBLIC_SENTINEL_API_KEY || "";

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
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
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
