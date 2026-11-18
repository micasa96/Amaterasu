// Same-origin JSON helper. Errors carry the server's message so pages can
// show it inline: FastAPI sends {"detail": "..."}; some routes send
// {"error": "..."} or {"message": "..."}.
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message);
  }
}

export async function api<T = unknown>(
  url: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(url, {
    credentials: "same-origin",
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  const text = await res.text();
  let body: unknown = text;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    /* plain-text body */
  }
  if (!res.ok) {
    const b = body as Record<string, unknown> | null;
    const detail =
      (b && typeof b === "object" && (b.detail || b.error || b.message)) ||
      (typeof body === "string" && body) ||
      res.statusText;
    throw new ApiError(
      typeof detail === "string" ? detail : `Request failed (${res.status})`,
      res.status,
      body,
    );
  }
  return body as T;
}

export function errorMessage(err: unknown, fallback = "Something went wrong. Try again."): string {
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
