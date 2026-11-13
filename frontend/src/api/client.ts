import axios from "axios";

import { storage } from "../utils/storage";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30000, // 30s default timeout
});

let accessToken: string | null = storage.getAccessToken();

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) {
    storage.setAccessToken(token);
  } else {
    storage.removeAccessToken();
  }
}

export function getAccessToken(): string | null {
  return accessToken || storage.getAccessToken();
}

/**
 * Create an AbortController and return { signal, cancel }.
 * Usage in components:
 *   const { signal, cancel } = createCancellable();
 *   apiClient.get("/path", { signal });
 *   // on unmount: cancel();
 */
export function createCancellable() {
  const controller = new AbortController();
  return {
    signal: controller.signal,
    cancel: () => controller.abort(),
  };
}

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Don't retry if request was cancelled
    if (axios.isCancel(error)) {
      return Promise.reject(error);
    }

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = storage.getRefreshToken();
      if (!refreshToken) {
        isRefreshing = false;
        window.location.href = "/login";
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
          refresh_token: refreshToken,
        });
        const { access_token, refresh_token } = response.data;
        setAccessToken(access_token);
        storage.setRefreshToken(refresh_token);
        processQueue(null, access_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        setAccessToken(null);
        storage.removeRefreshToken();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Map common HTTP errors to user-friendly messages
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;
      const message =
        data?.error?.message || data?.detail || data?.message;

      if (status === 403) {
        error.userMessage = message || "You don't have permission to perform this action.";
      } else if (status === 404) {
        error.userMessage = message || "The requested resource was not found.";
      } else if (status === 429) {
        error.userMessage = "Too many requests. Please wait a moment and try again.";
        error.retryAfter = error.response.headers?.["retry-after"];
      } else if (status === 503) {
        error.userMessage = "The service is temporarily unavailable. Please try again later.";
      } else if (status >= 500) {
        error.userMessage = "A server error occurred. Please try again later.";
      }
    } else if (error.code === "ECONNABORTED") {
      error.userMessage = "Request timed out. Please try again.";
    } else if (!error.response) {
      error.userMessage = "Network error. Please check your connection.";
    }

    return Promise.reject(error);
  },
);

export default apiClient;
