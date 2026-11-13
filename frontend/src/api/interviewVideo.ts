import { getAccessToken } from "./client";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Build the signaling WebSocket URL for one interview room.
 *
 * The access token rides in the query string because browsers cannot attach an
 * `Authorization` header to a WebSocket handshake; it is the *same* access
 * token the REST client sends, and the server re-runs the full room
 * authorization (tenant scoping, role, join window) before relaying anything,
 * so possessing this URL grants nothing the REST endpoints would not.
 *
 * The base mirrors `apiClient`'s: an absolute `VITE_API_BASE_URL` is used
 * verbatim (with its scheme swapped for ws/wss); otherwise the socket goes
 * same-origin, so the dev server's proxy and the production build both reach
 * the backend without extra configuration.
 */
export function videoSignalingUrl(interviewId: string): string {
  const token = getAccessToken() ?? "";
  const query = `?token=${encodeURIComponent(token)}`;
  const path = `/api/v1/interview/${interviewId}/video${query}`;

  if (API_BASE_URL) {
    return `${API_BASE_URL.replace(/^http/, "ws")}${path}`;
  }
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}${path}`;
}
