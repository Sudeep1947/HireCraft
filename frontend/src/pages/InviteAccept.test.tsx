/**
 * Tests for the shared invitation acceptance page (/invite/:token).
 *
 * What these tests protect:
 * - the page is reachable at /invite/:token and validates the token through
 *   the public backend endpoint with no auth required;
 * - both Recruiter and HR (hr_manager) invitations render the authoritative
 *   role from the invitation record, never a user-selected role;
 * - invalid / expired / revoked links show a controlled error, not a crash;
 * - the existing-user (sign-in required) flow gates acceptance on identity;
 * - the new-user acceptance flow shows role-specific onboarding copy and
 *   reports success once the backend accepts.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InviteAccept } from "./InviteAccept";

const mockValidateInvitation = vi.fn();
const mockAcceptInvitation = vi.fn();
const mockAcceptSignedInInvitation = vi.fn();

vi.mock("../api/auth", () => ({
  validateInvitation: (...args: unknown[]) => mockValidateInvitation(...args),
  acceptInvitation: (...args: unknown[]) => mockAcceptInvitation(...args),
  acceptSignedInInvitation: (...args: unknown[]) =>
    mockAcceptSignedInInvitation(...args),
}));

// The page reads the signed-in identity only for the existing-user branch.
let mockAuthState: { user: { email?: string } | null; isAuthenticated: boolean } =
  { user: null, isAuthenticated: false };

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => mockAuthState,
}));

const VALID_RECRUITER = {
  valid: true,
  email: "recruiter@example.com",
  role: "recruiter",
  organization_name: "Acme Corp",
  expires_at: "2026-12-31T00:00:00Z",
  status: "pending",
  existing_user: false,
};

function renderAtToken(token = "tok-req-abc") {
  return render(
    <MemoryRouter initialEntries={[`/invite/${token}`]}>
      <Routes>
        <Route path="/invite/:token" element={<InviteAccept />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockAuthState = { user: null, isAuthenticated: false };
  mockValidateInvitation.mockReset();
  mockAcceptInvitation.mockReset();
  mockAcceptSignedInInvitation.mockReset();
});

describe("InviteAccept — token validation", () => {
  it("waits (spinner) while the token is being validated — no form, no error yet", () => {
    mockValidateInvitation.mockReturnValue(new Promise(() => {}));
    renderAtToken();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Full Name")).not.toBeInTheDocument();
  });

  it("renders a controlled invalid-invitation state for a bad token", async () => {
    mockValidateInvitation.mockResolvedValue({ valid: false });
    renderAtToken("garbage");
    await screen.findByRole("alert");
    expect(screen.getByText(/Invalid Invitation/)).toBeInTheDocument();
    expect(
      screen.getByText(/invalid, expired, revoked, or has already been used/i),
    ).toBeInTheDocument();
  });
});

describe("InviteAccept — role from the invitation record", () => {
  it("renders the Recruiter role and new-user form (no auth needed)", async () => {
    mockValidateInvitation.mockResolvedValue(VALID_RECRUITER);
    renderAtToken();

    await screen.findByText(/Acme Corp/);
    expect(screen.getByText("Recruiter")).toBeInTheDocument();
    expect(screen.getByText(/recruiter@example\.com/)).toBeInTheDocument();
    expect(screen.getByLabelText("Full Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm Password")).toBeInTheDocument();
  });

  it("renders the HR Manager role from an hr_manager invitation", async () => {
    mockValidateInvitation.mockResolvedValue({
      ...VALID_RECRUITER,
      email: "hr@example.com",
      role: "hr_manager",
    });
    renderAtToken();

    await screen.findByText(/Acme Corp/);
    expect(screen.getByText("HR Manager")).toBeInTheDocument();
  });

  it("does not offer a role selector — the role is not user-selectable", async () => {
    mockValidateInvitation.mockResolvedValue(VALID_RECRUITER);
    renderAtToken();
    await screen.findByLabelText("Full Name");
    expect(screen.queryByLabelText("Role")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});

describe("InviteAccept — existing-user flow", () => {
  it("asks the invitee to sign in to accept (not authenticated)", async () => {
    mockValidateInvitation.mockResolvedValue({
      ...VALID_RECRUITER,
      email: "existing@example.com",
      existing_user: true,
    });
    renderAtToken();

    await screen.findByText(/An account already exists for this email/i);
    expect(
      screen.getByRole("link", { name: /Sign In to Accept Invitation/i }),
    ).toBeInTheDocument();
    expect(mockAcceptInvitation).not.toHaveBeenCalled();
  });

  it("accepts via accept-signed-in when the signed-in email matches the invite", async () => {
    mockAuthState = { user: { email: "existing@example.com" }, isAuthenticated: true };
    mockValidateInvitation.mockResolvedValue({
      ...VALID_RECRUITER,
      email: "existing@example.com",
      existing_user: true,
    });
    mockAcceptSignedInInvitation.mockResolvedValue(undefined);
    renderAtToken();

    const button = await screen.findByRole("button", {
      name: /Accept Invitation as existing@example.com/i,
    });
    await userEvent.click(button);

    await screen.findByText(/Invitation Accepted!/i);
    expect(mockAcceptSignedInInvitation).toHaveBeenCalledWith("tok-req-abc");
  });
});

describe("InviteAccept — new-user acceptance", () => {
  it("accepts, shows role-specific onboarding copy, and clears the form", async () => {
    mockValidateInvitation.mockResolvedValue(VALID_RECRUITER);
    mockAcceptInvitation.mockResolvedValue(undefined);
    renderAtToken();

    await userEvent.type(await screen.findByLabelText("Full Name"), "Ada Lovelace");
    await userEvent.type(screen.getByLabelText("Password"), "SecureP@ss1");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "SecureP@ss1");
    await userEvent.click(
      screen.getByRole("button", { name: /Accept Invitation & Create Account/i }),
    );

    await screen.findByText(/Invitation Accepted!/i);
    expect(screen.getByText(/onboarded as/i)).toBeInTheDocument();
    expect(screen.getByText("Recruiter", { selector: "strong" })).toBeInTheDocument();
    expect(mockAcceptInvitation).toHaveBeenCalledWith({
      token: "tok-req-abc",
      full_name: "Ada Lovelace",
      password: "SecureP@ss1",
      confirm_password: "SecureP@ss1",
    });
  });

  it("reports a backend failure instead of a success screen", async () => {
    mockValidateInvitation.mockResolvedValue(VALID_RECRUITER);
    mockAcceptInvitation.mockRejectedValue(new Error("Accept failed"));
    renderAtToken();

    await userEvent.type(await screen.findByLabelText("Full Name"), "Ada Lovelace");
    await userEvent.type(screen.getByLabelText("Password"), "SecureP@ss1");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "SecureP@ss1");
    await userEvent.click(
      screen.getByRole("button", { name: /Accept Invitation & Create Account/i }),
    );

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Accept failed"),
    );
    expect(screen.queryByText(/Invitation Accepted!/i)).not.toBeInTheDocument();
  });

  it("validates that passwords match before calling the backend", async () => {
    mockValidateInvitation.mockResolvedValue(VALID_RECRUITER);
    mockAcceptInvitation.mockResolvedValue(undefined);
    renderAtToken();

    await userEvent.type(await screen.findByLabelText("Full Name"), "Ada Lovelace");
    await userEvent.type(screen.getByLabelText("Password"), "SecureP@ss1");
    await userEvent.type(screen.getByLabelText("Confirm Password"), "SecureP@ss1X");
    await userEvent.click(
      screen.getByRole("button", { name: /Accept Invitation & Create Account/i }),
    );

    expect(await screen.findByText(/Passwords do not match/i)).toBeInTheDocument();
    expect(mockAcceptInvitation).not.toHaveBeenCalled();
  });
});