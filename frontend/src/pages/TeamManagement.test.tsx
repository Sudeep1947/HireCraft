import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as authApi from "../api/auth";
import type { Organization } from "../types/auth";
import { TeamManagement } from "./TeamManagement";

const authState = vi.hoisted(() => ({ roles: [] as string[] }));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    user: {
      id: "user-1",
      full_name: "Test User",
      email: "test@example.com",
      is_active: true,
      is_verified: true,
      roles: authState.roles,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

vi.mock("../api/auth", () => ({
  getMyOrganizations: vi.fn(),
  getOrgMembers: vi.fn(),
  getOrgInvitations: vi.fn(),
  createOrganization: vi.fn(),
  uploadOrganizationLogo: vi.fn(),
  inviteMember: vi.fn(),
  revokeInvitation: vi.fn(),
  resendInvitation: vi.fn(),
  updateMemberStatus: vi.fn(),
}));

const mockGetMyOrganizations = vi.mocked(authApi.getMyOrganizations);
const mockGetOrgMembers = vi.mocked(authApi.getOrgMembers);
const mockGetOrgInvitations = vi.mocked(authApi.getOrgInvitations);
const mockCreateOrganization = vi.mocked(authApi.createOrganization);
const mockUploadOrganizationLogo = vi.mocked(authApi.uploadOrganizationLogo);

function makeOrg(overrides: Partial<Organization> = {}): Organization {
  return {
    id: "org-1",
    name: "Existing Org",
    slug: "existing-org",
    industry: "Technology",
    website: "https://example.com",
    location: "Bangalore, India",
    status: "active",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  authState.roles = [];
  mockGetMyOrganizations.mockResolvedValue([]);
  mockGetOrgMembers.mockResolvedValue({ items: [], total: 0 });
  mockGetOrgInvitations.mockResolvedValue({ items: [], total: 0 });
});

describe("TeamManagement – organization creation access", () => {
  it("shows creation controls to a platform super admin", async () => {
    authState.roles = ["super_admin"];

    render(<TeamManagement />);

    const createBtn = await screen.findByRole("button", {
      name: /\+ create organization/i,
    });
    expect(createBtn).toBeInTheDocument();

    // Clicking button opens the creation form/modal
    await userEvent.click(createBtn);
    expect(
      await screen.findByRole("heading", { name: /create organization/i }),
    ).toBeInTheDocument();
  });

  it("treats legacy admin as a platform administrator", async () => {
    authState.roles = ["admin"];

    render(<TeamManagement />);

    const createBtn = await screen.findByRole("button", {
      name: /\+ create organization/i,
    });
    expect(createBtn).toBeInTheDocument();
    await userEvent.click(createBtn);
    expect(
      await screen.findByRole("heading", { name: /create organization/i }),
    ).toBeInTheDocument();
  });

  it("does not show creation controls to an organization admin without organizations", async () => {
    authState.roles = ["organization_admin"];

    render(<TeamManagement />);

    expect(await screen.findByText(/no organizations found/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /create organization/i }),
    ).not.toBeInTheDocument();
  });

  it("does not show creation controls to an organization admin who has an org", async () => {
    authState.roles = ["organization_admin"];
    mockGetMyOrganizations.mockResolvedValue([makeOrg()]);

    render(<TeamManagement />);

    expect(await screen.findByText(/invite team member to existing org/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /create organization/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps creation controls visible to a platform admin who already has orgs", async () => {
    authState.roles = ["super_admin"];
    mockGetMyOrganizations.mockResolvedValue([makeOrg()]);

    render(<TeamManagement />);

    expect(
      await screen.findByRole("button", { name: /\+ create organization/i }),
    ).toBeInTheDocument();
  });
});

describe("TeamManagement – organization creation flow", () => {
  it("trims input, creates the org, refreshes the list and reports success", async () => {
    authState.roles = ["super_admin"];
    const created = makeOrg({
      id: "org-new",
      name: "Acme Corp",
      slug: "acme-corp",
      industry: "Information Technology",
      website: "https://acme.example.com",
      location: "San Francisco, CA",
      status: "active",
    });
    mockGetMyOrganizations
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([created]); // refresh after create
    mockCreateOrganization.mockResolvedValueOnce(created);

    render(<TeamManagement />);

    // Open creation modal
    const openBtn = await screen.findByRole("button", {
      name: /\+ create organization/i,
    });
    await userEvent.click(openBtn);

    const nameInput = await screen.findByLabelText(/organization name/i);
    const slugInput = screen.getByLabelText(/slug/i);
    const industryInput = screen.getByLabelText(/industry/i);
    const websiteInput = screen.getByLabelText(/company website/i);
    const locationInput = screen.getByLabelText(/headquarters \/ location/i);

    await userEvent.type(nameInput, "  Acme Corp  ");
    expect(slugInput).toHaveValue("acme-corp");

    await userEvent.type(industryInput, "Information Technology");
    await userEvent.type(websiteInput, "https://acme.example.com");
    await userEvent.type(locationInput, "San Francisco, CA");

    // Click submit inside form
    const submitBtn = screen.getByRole("button", { name: /^create organization$/i });
    await userEvent.click(submitBtn);

    await waitFor(() =>
      expect(mockCreateOrganization).toHaveBeenCalledWith({
        name: "Acme Corp",
        slug: "acme-corp",
        industry: "Information Technology",
        website: "https://acme.example.com",
        location: "San Francisco, CA",
        description: undefined,
        status: "active",
        logo_url: undefined,
      }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      /Acme Corp.*created successfully/i,
    );
    expect(mockGetMyOrganizations).toHaveBeenCalledTimes(2);

    // Organization appears in the layout
    expect(await screen.findByRole("heading", { name: "Acme Corp" })).toBeInTheDocument();
    expect(screen.getByText("Information Technology")).toBeInTheDocument();
    expect(screen.getByText("San Francisco, CA")).toBeInTheDocument();
  });

  it("handles logo upload before organization creation", async () => {
    authState.roles = ["super_admin"];
    const created = makeOrg({
      id: "org-logo",
      name: "Logo Corp",
      slug: "logo-corp",
      logo_url: "/uploads/organizations/test-logo.png",
    });
    mockGetMyOrganizations.mockResolvedValueOnce([]).mockResolvedValueOnce([created]);
    mockUploadOrganizationLogo.mockResolvedValueOnce({
      logo_url: "/uploads/organizations/test-logo.png",
    });
    mockCreateOrganization.mockResolvedValueOnce(created);

    render(<TeamManagement />);

    const openBtn = await screen.findByRole("button", { name: /\+ create organization/i });
    await userEvent.click(openBtn);

    await userEvent.type(await screen.findByLabelText(/organization name/i), "Logo Corp");

    const file = new File(["dummy png content"], "logo.png", { type: "image/png" });
    const logoInput = screen.getByLabelText(/organization logo/i);
    await userEvent.upload(logoInput, file);

    const submitBtn = screen.getByRole("button", { name: /^create organization$/i });
    await userEvent.click(submitBtn);

    await waitFor(() => expect(mockUploadOrganizationLogo).toHaveBeenCalledWith(file));
    expect(mockCreateOrganization).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Logo Corp",
        slug: "logo-corp",
        logo_url: "/uploads/organizations/test-logo.png",
      }),
    );
  });

  it("shows server validation/conflict errors and does not refresh", async () => {
    authState.roles = ["super_admin"];
    mockCreateOrganization.mockRejectedValueOnce({
      response: {
        data: { detail: "Organization with this name already exists" },
      },
    });

    render(<TeamManagement />);

    await userEvent.click(await screen.findByRole("button", { name: /\+ create organization/i }));

    await userEvent.type(
      await screen.findByLabelText(/organization name/i),
      "Duplicate Corp",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /^create organization$/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Organization with this name already exists",
    );
    expect(mockGetMyOrganizations).toHaveBeenCalledTimes(1);
  });

  it("validates an empty organization name before calling the API", async () => {
    authState.roles = ["super_admin"];

    render(<TeamManagement />);

    await userEvent.click(await screen.findByRole("button", { name: /\+ create organization/i }));

    await userEvent.type(
      await screen.findByLabelText(/organization name/i),
      "   ",
    );
    fireEvent.submit(
      screen
        .getByRole("button", { name: /^create organization$/i })
        .closest("form")!,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /organization name is required/i,
    );
    expect(mockCreateOrganization).not.toHaveBeenCalled();
  });

  it("validates an invalid slug before calling the API", async () => {
    authState.roles = ["super_admin"];

    render(<TeamManagement />);

    await userEvent.click(await screen.findByRole("button", { name: /\+ create organization/i }));

    await userEvent.type(
      await screen.findByLabelText(/organization name/i),
      "Slug Check",
    );
    const slugInput = screen.getByLabelText(/slug/i);
    await userEvent.clear(slugInput);
    await userEvent.type(slugInput, "bad--slug");
    await userEvent.click(
      screen.getByRole("button", { name: /^create organization$/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /single hyphens/i,
    );
    expect(mockCreateOrganization).not.toHaveBeenCalled();
  });

  it("validates website URL format before calling the API", async () => {
    authState.roles = ["super_admin"];

    render(<TeamManagement />);

    await userEvent.click(await screen.findByRole("button", { name: /\+ create organization/i }));

    await userEvent.type(
      await screen.findByLabelText(/organization name/i),
      "URL Check Corp",
    );
    const websiteInput = screen.getByLabelText(/company website/i);
    await userEvent.type(websiteInput, "invalid-url-format");

    await userEvent.click(
      screen.getByRole("button", { name: /^create organization$/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /invalid website url format/i,
    );
    expect(mockCreateOrganization).not.toHaveBeenCalled();
  });

  it("allows canceling the organization creation modal", async () => {
    authState.roles = ["super_admin"];

    render(<TeamManagement />);

    await userEvent.click(await screen.findByRole("button", { name: /\+ create organization/i }));
    expect(
      await screen.findByRole("heading", { name: /create organization/i }),
    ).toBeInTheDocument();

    const cancelBtn = screen.getByRole("button", { name: /cancel/i });
    await userEvent.click(cancelBtn);

    expect(
      screen.queryByRole("heading", { name: /create organization/i }),
    ).not.toBeInTheDocument();
  });

  it("prevents duplicate submissions while a create is in flight", async () => {
    authState.roles = ["super_admin"];
    const created = makeOrg({
      id: "org-double",
      name: "Double Click Corp",
      slug: "double-click-corp",
    });

    let resolveCreate!: (value: Organization) => void;
    mockCreateOrganization.mockReturnValueOnce(
      new Promise<Organization>((resolve) => {
        resolveCreate = resolve;
      }),
    );

    render(<TeamManagement />);

    await userEvent.click(await screen.findByRole("button", { name: /\+ create organization/i }));

    await userEvent.type(
      await screen.findByLabelText(/organization name/i),
      "Double Click Corp",
    );
    const form = screen
      .getByRole("button", { name: /^create organization$/i })
      .closest("form")!;

    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(mockCreateOrganization).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /^create organization$/i }),
      ).toBeDisabled(),
    );

    resolveCreate(created);

    expect(await screen.findByRole("status")).toHaveTextContent(
      /Double Click Corp.*created successfully/i,
    );
    expect(mockCreateOrganization).toHaveBeenCalledTimes(1);
  });
});
