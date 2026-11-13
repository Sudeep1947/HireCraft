/**
 * The candidate's own account id, shown on their profile.
 *
 * This is the id a recruiter calls "Candidate ID", so it has to come from
 * `users.id` -- not from the candidate profile row, which is a different uuid
 * and the single most likely thing to get wrong here.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { candidateApi } from "../../api/candidate";
import { CandidateProfile } from "./Profile";

const CANDIDATE_ID = "2a91f6d3-7c91-4f2b-9a3e-1c8d5e0b7a44";

vi.mock("../../api/candidate", () => ({
  candidateApi: {
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    uploadAvatar: vi.fn(),
    removeAvatar: vi.fn(),
  },
}));

// Mutable so a test can stand in a session that has gone away. `vi.hoisted`
// because the mock factory runs before module-level declarations.
const { authState } = vi.hoisted(() => ({
  authState: {
    user: {
      id: "2a91f6d3-7c91-4f2b-9a3e-1c8d5e0b7a44",
      email: "john@example.com",
      full_name: "John Doe",
      role: "candidate",
    } as { id: string; email: string; full_name: string; role: string } | null,
  },
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: authState.user,
    updateProfile: vi.fn(),
    isAuthenticated: authState.user !== null,
  }),
}));

const addToast = vi.fn();
vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ addToast }),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <CandidateProfile />
    </MemoryRouter>,
  );
}

describe("Profile candidate id", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.user = {
      id: CANDIDATE_ID,
      email: "john@example.com",
      full_name: "John Doe",
      role: "candidate",
    };
    // The page renders a spinner until the profile lands, so the identifier
    // block is only reachable after this resolves.
    vi.mocked(candidateApi.getProfile).mockResolvedValue({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      full_name: "John Doe",
    } as never);
  });

  it("shows the signed-in user's id, labelled as their candidate id", async () => {
    renderPage();
    expect(
      await screen.findByText("Candidate ID", { selector: "label" }),
    ).toBeInTheDocument();
    expect(screen.getByTitle(CANDIDATE_ID)).toBeInTheDocument();
  });

  it("uses the session id, not the candidate profile row's own id", async () => {
    renderPage();
    await screen.findByText("Your identifiers");

    // Both uuids are in play on this page. Labelling the profile row's id as the
    // candidate id would send support looking for an id the recruiter has never
    // seen, so the one shown must be the session's.
    expect(screen.getByTitle(CANDIDATE_ID)).toBeInTheDocument();
    expect(
      screen.queryByTitle("7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71"),
    ).not.toBeInTheDocument();
  });

  it("explains where the id comes from, so it is not mistaken for another id", async () => {
    renderPage();
    // The distinction between users.id and the profile row's own id is the
    // whole reason this line of copy is here.
    expect(
      await screen.findByText(/identifies your account, across all your applications/i),
    ).toBeInTheDocument();
  });

  it("copies the full id for pasting into a support email", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
      writable: true,
    });
    renderPage();
    await screen.findByText("Your identifiers");

    await userEvent.click(
      await screen.findByRole("button", { name: /copy candidate id/i }),
    );
    expect(writeText).toHaveBeenCalledWith(CANDIDATE_ID);
  });

  it("hides the block when there is no signed-in id, rather than showing an empty one", async () => {
    // A session that has expired mid-visit. An empty "Candidate ID" row would
    // be worse than none, since it invites the reader to go looking for it.
    authState.user = null;
    renderPage();
    await screen.findByText("Avatar");
    expect(
      screen.queryByText("Candidate ID", { selector: "label" }),
    ).not.toBeInTheDocument();
  });
});

describe("Candidate Profile Photo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.user = {
      id: CANDIDATE_ID,
      email: "john@example.com",
      full_name: "John Doe",
      role: "candidate",
    };
  });

  it("displays sensible placeholder with initials when no photo exists", async () => {
    vi.mocked(candidateApi.getProfile).mockResolvedValueOnce({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      avatar_url: null,
    } as never);
    renderPage();

    expect(await screen.findByText("Upload Photo")).toBeInTheDocument();
    expect(screen.getByText("JD")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /profile photo/i })).not.toBeInTheDocument();
  });

  it("displays profile photo and Change/Remove buttons when photo exists", async () => {
    vi.mocked(candidateApi.getProfile).mockResolvedValueOnce({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      avatar_url: "/uploads/avatars/user.jpg",
    } as never);
    renderPage();

    expect(await screen.findByRole("img", { name: /profile photo/i })).toBeInTheDocument();
    expect(screen.getByText("Change Photo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove/i })).toBeInTheDocument();
  });

  it("validates file format and rejects unsupported formats with an error message", async () => {
    vi.mocked(candidateApi.getProfile).mockResolvedValueOnce({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      avatar_url: null,
    } as never);
    renderPage();

    await screen.findByText("Upload Photo");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    const invalidFile = new File(["dummy content"], "resume.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [invalidFile] } });

    expect(candidateApi.uploadAvatar).not.toHaveBeenCalled();
    expect(await screen.findByText(/invalid file format/i)).toBeInTheDocument();
  });

  it("validates file size limit and rejects files over 5 MB", async () => {
    vi.mocked(candidateApi.getProfile).mockResolvedValueOnce({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      avatar_url: null,
    } as never);
    renderPage();

    await screen.findByText("Upload Photo");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    // Create file > 5 MB
    const largeBlob = new Blob([new Uint8Array(6 * 1024 * 1024)]);
    const largeFile = new File([largeBlob], "huge.png", { type: "image/png" });
    await userEvent.upload(input, largeFile);

    expect(candidateApi.uploadAvatar).not.toHaveBeenCalled();
    expect(await screen.findByText(/file size exceeds 5 mb limit/i)).toBeInTheDocument();
  });

  it("successfully uploads a valid photo and updates profile image", async () => {
    vi.mocked(candidateApi.getProfile).mockResolvedValueOnce({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      avatar_url: null,
    } as never);
    vi.mocked(candidateApi.uploadAvatar).mockResolvedValueOnce({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      avatar_url: "/uploads/avatars/uploaded.png",
    } as never);

    renderPage();
    await screen.findByText("Upload Photo");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    const validFile = new File(["image-bytes"], "photo.png", { type: "image/png" });
    await userEvent.upload(input, validFile);

    expect(candidateApi.uploadAvatar).toHaveBeenCalledWith(validFile);
    expect(await screen.findByText("Profile photo updated successfully")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /profile photo/i })).toBeInTheDocument();
  });

  it("removes profile photo when Remove is clicked", async () => {
    vi.mocked(candidateApi.getProfile).mockResolvedValueOnce({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      avatar_url: "/uploads/avatars/user.jpg",
    } as never);
    vi.mocked(candidateApi.removeAvatar).mockResolvedValueOnce({
      id: "7d2f4c88-51a9-4e37-b6d2-9f0a3c8e5b71",
      avatar_url: null,
    } as never);

    renderPage();
    const removeBtn = await screen.findByRole("button", { name: /remove/i });
    await userEvent.click(removeBtn);

    expect(candidateApi.removeAvatar).toHaveBeenCalled();
    expect(await screen.findByText("Profile photo removed successfully")).toBeInTheDocument();
  });
});
