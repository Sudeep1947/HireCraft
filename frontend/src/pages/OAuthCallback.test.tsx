import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as authApi from "../api/auth";
import { AuthContext } from "../contexts/AuthContext";
import type { RoleName, User } from "../types/auth";
import { OAuthCallback } from "./OAuthCallback";

vi.mock("../api/auth", () => ({
  oauthCallback: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  refreshToken: vi.fn(),
  getMe: vi.fn(),
  logout: vi.fn(),
}));

const mockHandleOAuthSuccess = vi.fn();
const mockUser: User = {
  id: "u-123",
  full_name: "OAuth User",
  email: "oauth@example.com",
  is_active: true,
  is_verified: true,
  roles: ["candidate"] as RoleName[],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderCallback(initialEntry: string) {
  return render(
    <AuthContext.Provider
      value={{
        user: null,
        accessToken: null,
        isAuthenticated: false,
        isLoading: false,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        refreshAuth: vi.fn(),
        handleOAuthSuccess: mockHandleOAuthSuccess,
        permissions: new Set(),
        can: () => false,
      }}
    >
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/auth/callback/:provider" element={<OAuthCallback />} />
          <Route path="/candidate/dashboard" element={<div>Candidate Dashboard View</div>} />
          <Route path="/skill2job" element={<div>Candidate Dashboard View</div>} />
          <Route path="/admin/dashboard" element={<div>Admin Dashboard View</div>} />
          <Route path="/login" element={<div>Login View</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("OAuthCallback Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("handles user denial or cancellation gracefully", async () => {
    renderCallback("/auth/callback/google?error=access_denied&error_description=Consent+denied");

    expect(await screen.findByText(/Authentication Failed/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Google Sign-In was cancelled or access was denied/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /return to sign in/i })).toBeInTheDocument();
  });

  it("handles missing authorization code with friendly message", async () => {
    renderCallback("/auth/callback/microsoft");

    expect(await screen.findByText(/Authentication Failed/i)).toBeInTheDocument();
    expect(
      screen.getByText(/No authorization code returned from Microsoft/i),
    ).toBeInTheDocument();
  });

  it("successfully exchanges code and redirects candidate to candidate dashboard", async () => {
    vi.mocked(authApi.oauthCallback).mockResolvedValueOnce({
      access_token: "mock-access-token",
      refresh_token: "mock-refresh-token",
      token_type: "bearer",
      user: mockUser,
    });
    mockHandleOAuthSuccess.mockResolvedValueOnce(mockUser);

    renderCallback("/auth/callback/google?code=valid-auth-code&state=xyz");

    expect(await screen.findByText("Candidate Dashboard View")).toBeInTheDocument();
    expect(authApi.oauthCallback).toHaveBeenCalledWith("google", {
      code: "valid-auth-code",
      state: "xyz",
      redirect_uri: expect.stringContaining("/auth/callback/google"),
    });
    expect(mockHandleOAuthSuccess).toHaveBeenCalled();
  });

  it("successfully redirects admin user to admin dashboard", async () => {
    const adminUser = { ...mockUser, roles: ["admin" as RoleName] };
    vi.mocked(authApi.oauthCallback).mockResolvedValueOnce({
      access_token: "mock-access-token",
      refresh_token: "mock-refresh-token",
      token_type: "bearer",
      user: adminUser,
    });
    mockHandleOAuthSuccess.mockResolvedValueOnce(adminUser);

    renderCallback("/auth/callback/microsoft?code=admin-ms-code&state=xyz");

    expect(await screen.findByText("Admin Dashboard View")).toBeInTheDocument();
  });

  it("shows error if backend callback rejects with an error", async () => {
    vi.mocked(authApi.oauthCallback).mockRejectedValueOnce({
      response: {
        data: {
          detail: "Google authentication failed: invalid or expired authorization code",
        },
      },
    });

    renderCallback("/auth/callback/google?code=expired-code");

    expect(
      await screen.findByRole("heading", { name: /authentication failed/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/invalid or expired authorization code/i),
    ).toBeInTheDocument();
  });
});
