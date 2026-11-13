import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Login } from "./Login";

const mockLogin = vi.fn();
const mockHandleOAuthSuccess = vi.fn();
const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    login: mockLogin,
    handleOAuthSuccess: mockHandleOAuthSuccess,
    isAuthenticated: false,
    user: null,
  }),
}));

vi.mock("../api/auth", () => ({
  devOAuthLogin: vi.fn().mockResolvedValue({
    access_token: "mock-token",
    refresh_token: "mock-refresh",
    user: { id: "u-1", email: "miniprojectcse000@gmail.com", roles: ["hr_manager"] },
  }),
  getOAuthUrl: vi.fn(),
}));

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  );
}

describe("Login Page - Back to Home & Authentication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a clearly visible Back to Home link pointing to root /", () => {
    renderLogin();
    const backToHome = screen.getByRole("link", { name: /back to home/i });
    expect(backToHome).toBeInTheDocument();
    expect(backToHome).toHaveAttribute("href", "/");
  });

  it("renders the login form with email and password inputs", () => {
    renderLogin();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("validates empty submission and shows validation errors", async () => {
    renderLogin();
    const signInBtn = screen.getByRole("button", { name: /sign in/i });
    await userEvent.click(signInBtn);
    expect(mockLogin).not.toHaveBeenCalled();
    expect(screen.getByText(/invalid email address/i)).toBeInTheDocument();
  });

  it("submits the credentials when form is valid", async () => {
    mockLogin.mockResolvedValueOnce({ roles: ["candidate"] });
    renderLogin();

    await userEvent.type(screen.getByLabelText(/email/i), "candidate@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(mockLogin).toHaveBeenCalledWith({
      email: "candidate@example.com",
      password: "password123",
      remember_me: false,
    });
  });

  it("navigates HR Manager to /hr/dashboard after successful login", async () => {
    mockLogin.mockResolvedValueOnce({ roles: ["hr_manager"] });
    renderLogin();

    await userEvent.type(screen.getByLabelText(/email/i), "hr@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(mockNavigate).toHaveBeenCalledWith("/hr/dashboard");
  });

  it("navigates HR role to /hr/dashboard after successful login", async () => {
    mockLogin.mockResolvedValueOnce({ roles: ["hr"] });
    renderLogin();

    await userEvent.type(screen.getByLabelText(/email/i), "hr@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(mockNavigate).toHaveBeenCalledWith("/hr/dashboard");
  });

  it("opens Google Sign-In account chooser when clicking Sign in with Google", async () => {
    renderLogin();
    const googleBtn = screen.getByRole("button", { name: /google/i });
    await userEvent.click(googleBtn);

    expect(screen.getByText(/choose an account to continue to skill2job/i)).toBeInTheDocument();
    expect(screen.getByText("miniprojectcse000@gmail.com")).toBeInTheDocument();
  });

  it("opens Microsoft Sign-In account chooser when clicking Sign in with Microsoft", async () => {
    renderLogin();
    const msBtn = screen.getByRole("button", { name: /microsoft/i });
    await userEvent.click(msBtn);

    expect(screen.getByText(/pick an account to continue to skill2job/i)).toBeInTheDocument();
  });

  it("logs in with selected Google account and navigates to dashboard", async () => {
    mockHandleOAuthSuccess.mockResolvedValueOnce({ roles: ["hr_manager"] });
    renderLogin();
    const googleBtn = screen.getByRole("button", { name: /google/i });
    await userEvent.click(googleBtn);

    const harishOption = screen.getByText("miniprojectcse000@gmail.com");
    await userEvent.click(harishOption);

    expect(mockHandleOAuthSuccess).toHaveBeenCalled();
  });
});
