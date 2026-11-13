import type { AxiosError } from "axios";

interface ServerError {
  detail?: string | Array<{ msg?: string; detail?: string }>;
  code?: string;
  error?: { message?: string };
}

export function getErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === "object" && "isAxiosError" in err) {
    const axiosErr = err as AxiosError<ServerError>;
    const nestedMessage = axiosErr.response?.data?.error?.message;
    if (typeof nestedMessage === "string") return nestedMessage;
    const detail = axiosErr.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((e) => e.msg || e.detail || "").join(", ");
    }
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

/**
 * The server's deliberate message, or the caller's fallback -- never the raw
 * exception text.
 *
 * `getErrorMessage` falls back to `err.message`, which for a dropped connection
 * is "Network Error" and for anything thrown locally is whatever that code put
 * there. Neither tells a user what to do next, and neither is guaranteed to be
 * free of internals. An HTTP response is the only case where the message was
 * written to be read by a user, so only then is it echoed back.
 *
 * Use this for anything rendered to a user. Reach for `getErrorMessage` only
 * when surfacing the underlying message is the point, such as logging.
 */
export function getServerErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === "object" && "response" in err) {
    const { response } = err as {
      response?: { data?: { error?: { message?: unknown }; detail?: unknown } };
    };
    const detail = response?.data?.error?.message ?? response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    // FastAPI reports 422s as a list of per-field problems. Naming the fields
    // is the whole point of showing the message, so it is not dropped for a
    // generic "something was wrong".
    if (Array.isArray(detail)) {
      const messages = detail
        .map((e) =>
          e && typeof e === "object"
            ? ((e as { msg?: unknown }).msg ?? (e as { detail?: unknown }).detail)
            : undefined,
        )
        .filter((m): m is string => typeof m === "string" && m.trim().length > 0);
      if (messages.length) return messages.join(", ");
    }
  }
  return fallback;
}
