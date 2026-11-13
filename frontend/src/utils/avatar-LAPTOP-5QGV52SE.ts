/**
 * Helper to resolve avatar / profile photo URLs.
 * Handles both absolute external URLs and relative backend paths (like /uploads/avatars/...),
 * respecting VITE_API_BASE_URL when defined, and optionally attaching a cache-busting parameter.
 */
export function resolveAvatarUrl(
  url: string | null | undefined,
  version?: number | string,
): string | null {
  if (!url) return null;
  let fullUrl = url;

  if (
    !url.startsWith("http://") &&
    !url.startsWith("https://") &&
    !url.startsWith("data:")
  ) {
    const apiBase = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
    if (apiBase) {
      fullUrl = `${apiBase}${url.startsWith("/") ? "" : "/"}${url}`;
    }
  }

  if (version !== undefined) {
    const sep = fullUrl.includes("?") ? "&" : "?";
    fullUrl = `${fullUrl}${sep}v=${version}`;
  }

  return fullUrl;
}
