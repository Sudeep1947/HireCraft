import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProtectedRoute } from "./ProtectedRoute";
import type { User } from "../types/auth";

let mockUser: User | null = null;
let mockIsAuthenticated = false;
let mockIsLoading = false;

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    user: mockUser,
    isAuthenticated: mockIsAuthenticated,
    isLoading: mockIsLoading,
  }),
}));

function renderProtected(roles?: ("hr" | "hr_manager" | "candidate" | "recruiter" | "admin")[]) {
  return render(
    <MemoryRouter initialEntries={["/test"]}>
      <Routes>
        <Route
          path="/test"
          element={
            <ProtectedRoute roles={roles}>
              <div data-testid="protected-content">Secret Content</div>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<div>Login Page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute Role Authorization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = null;
    mockIsAuthenticated = false;
    mockIsLoading = false;
  });

  it("redirects unauthenticated user to /login", () => {
    renderProtected(["hr_manager"]);
    expect(screen.getByText("Login Page")).toBeInTheDocument();
  });

  it("permits HR Manager with role 'hr_manager' to access a route requiring 'hr_manager'", () => {
    mockIsAuthenticated = true;
    mockUser = {
      id: "u1",
      full_name: "Harper Reed",
      email: "hr@example.com",
      is_active: true,
      is_verified: true,
      roles: ["hr_manager"],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    renderProtected(["hr_manager"]);
    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("permits HR Manager with role 'hr_manager' to access a route requiring alias 'hr'", () => {
    mockIsAuthenticated = true;
    mockUser = {
      id: "u1",
      full_name: "Harper Reed",
      email: "hr@example.com",
      is_active: true,
      is_verified: true,
      roles: ["hr_manager"],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    renderProtected(["hr"]);
    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("permits HR user with role 'hr' to access a route requiring 'hr_manager'", () => {
    mockIsAuthenticated = true;
    mockUser = {
      id: "u1",
      full_name: "Harper Reed",
      email: "hr@example.com",
      is_active: true,
      is_verified: true,
      roles: ["hr"],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    renderProtected(["hr_manager"]);
    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("blocks HR Manager when accessing a candidate-only route and shows Access Denied with Required Access: Role: Candidate", () => {
    mockIsAuthenticated = true;
    mockUser = {
      id: "u1",
      full_name: "Harper Reed",
      email: "hr@example.com",
      is_active: true,
      is_verified: true,
      roles: ["hr_manager"],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    renderProtected(["candidate"]);
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
    expect(screen.getByText("Access Denied")).toBeInTheDocument();
    expect(screen.getByText(/Role: Candidate/)).toBeInTheDocument();
    expect(screen.getByText(/Your role: HR Manager/)).toBeInTheDocument();
  });

  it("blocks candidate when accessing an HR-only route", () => {
    mockIsAuthenticated = true;
    mockUser = {
      id: "u2",
      full_name: "Casey Candidate",
      email: "candidate@example.com",
      is_active: true,
      is_verified: true,
      roles: ["candidate"],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    renderProtected(["hr_manager"]);
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
    expect(screen.getByText("Access Denied")).toBeInTheDocument();
  });
});
