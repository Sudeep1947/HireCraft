import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationIdentityCard } from "./ApplicationIdentityCard";
import { IdentifierField, IdentifierGrid } from "./IdentifierField";

// A real-shaped UUID: 36 characters, so the truncation path is genuinely
// exercised rather than a string short enough to skip it.
const CANDIDATE_ID = "2a91f6d3-7c91-4f2b-9a3e-1c8d5e0b7a44";
const APPLICATION_ID = "8f4c2b91-3d6e-4a58-b0f1-92c7e6d4a803";

function mockClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
    writable: true,
  });
  return writeText;
}

describe("IdentifierField", () => {
  afterEach(() => {
    // Undo any global stub so one test's clipboard cannot leak into the next.
    Object.defineProperty(navigator, "clipboard", {
      value: undefined,
      configurable: true,
      writable: true,
    });
  });

  it("labels the identifier, so a UUID is never shown unexplained", () => {
    render(<IdentifierField label="Candidate ID" value={CANDIDATE_ID} />);
    expect(
      screen.getByText("Candidate ID", { selector: "label" }),
    ).toBeInTheDocument();
  });

  it("truncates for display but never truncates what it copies", async () => {
    const writeText = mockClipboard();
    render(<IdentifierField label="Candidate ID" value={CANDIDATE_ID} copyable />);

    const displayed = screen.getByTitle(CANDIDATE_ID);
    // Abbreviated on screen...
    expect(displayed).not.toHaveTextContent(CANDIDATE_ID);
    expect(displayed.textContent).toContain(CANDIDATE_ID.slice(0, 13));
    // ...and the full value is still available without hovering.
    expect(displayed).toHaveAttribute("title", CANDIDATE_ID);

    // The clipboard receives the complete identifier, not the abbreviation.
    await userEvent.click(screen.getByRole("button", { name: /copy candidate id/i }));
    expect(writeText).toHaveBeenCalledWith(CANDIDATE_ID);
  });

  it("shows a quiet 'Copied' confirmation instead of an intrusive notification", async () => {
    mockClipboard();
    render(<IdentifierField label="Application ID" value={APPLICATION_ID} copyable />);

    const button = screen.getByRole("button", { name: /copy application id/i });
    await userEvent.click(button);

    expect(await screen.findByText("Copied")).toBeInTheDocument();
    // The confirmation is announced, not only drawn.
    expect(
      screen.getByText("Application ID copied to clipboard"),
    ).toBeInTheDocument();
  });

  it("clears the confirmation on its own, so a stale 'Copied' cannot mislead", async () => {
    mockClipboard();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<IdentifierField label="Application ID" value={APPLICATION_ID} copyable />);

    await userEvent.click(
      screen.getByRole("button", { name: /copy application id/i }),
    );
    expect(await screen.findByText("Copied")).toBeInTheDocument();

    // Advancing the reset timer has to happen inside act: it drives a state
    // update in the component.
    await act(async () => {
      vi.advanceTimersByTime(2500);
    });
    expect(screen.queryByText("Copied")).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("reports a failed copy rather than claiming it succeeded", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
      configurable: true,
      writable: true,
    });
    render(<IdentifierField label="Candidate ID" value={CANDIDATE_ID} copyable />);

    await userEvent.click(screen.getByRole("button", { name: /copy candidate id/i }));

    expect(await screen.findByText("Copy failed")).toBeInTheDocument();
    expect(
      screen.getByText("Could not copy candidate id"),
    ).toBeInTheDocument();
  });

  it("copies through a fallback when the Clipboard API is unavailable", async () => {
    // Insecure origins and older engines have no navigator.clipboard. A copy
    // button that silently does nothing there is worse than a degrading one.
    Object.defineProperty(navigator, "clipboard", {
      value: undefined,
      configurable: true,
      writable: true,
    });
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", {
      value: execCommand,
      configurable: true,
      writable: true,
    });

    render(<IdentifierField label="Candidate ID" value={CANDIDATE_ID} copyable />);
    await userEvent.click(screen.getByRole("button", { name: /copy candidate id/i }));

    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("keeps the copy button reachable and described for assistive technology", () => {
    render(<IdentifierField label="Interview ID" value="int-1" copyable />);
    const button = screen.getByRole("button", { name: "Copy interview id" });
    // Keyboard reachable (a real button, not a click handler on a div) and it
    // says which identifier it copies, so two adjacent ones are distinguishable.
    expect(button.tagName).toBe("BUTTON");
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("title", "Copy interview id");
  });

  it("renders nothing when there is no value, so 'None' never reads as an id", () => {
    const { container } = render(
      <IdentifierField label="Application ID" value={null} copyable />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a short value in full rather than abbreviating it pointlessly", () => {
    render(<IdentifierField label="Interview ID" value="int-1" />);
    expect(screen.getByTitle("int-1")).toHaveTextContent("int-1");
  });

  it("can render the whole value when space allows", () => {
    render(<IdentifierField label="Candidate ID" value={CANDIDATE_ID} fullWidth />);
    expect(screen.getByTitle(CANDIDATE_ID)).toHaveTextContent(CANDIDATE_ID);
  });

  it("omits the copy button when the identifier is not copyable", () => {
    render(<IdentifierField label="Job ID" value="job-1" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("IdentifierGrid", () => {
  it("keeps the four workflow identifiers distinct and labelled", () => {
    render(
      <IdentifierGrid
        items={[
          { label: "Candidate ID", value: CANDIDATE_ID },
          { label: "Application ID", value: APPLICATION_ID },
          { label: "Job ID", value: "job-1" },
          { label: "Interview ID", value: "int-1" },
        ]}
      />,
    );
    for (const label of ["Candidate ID", "Application ID", "Job ID", "Interview ID"]) {
      expect(screen.getByText(label, { selector: "label" })).toBeInTheDocument();
    }
  });

  it("drops entries with no value instead of rendering an empty labelled field", () => {
    render(
      <IdentifierGrid
        items={[
          { label: "Application ID", value: APPLICATION_ID },
          { label: "Interview ID", value: null },
        ]}
      />,
    );
    expect(screen.queryByText("Interview ID")).not.toBeInTheDocument();
  });
});

describe("ApplicationIdentityCard", () => {
  it("shows the candidate, the job, the status and every identifier together", () => {
    render(
      <ApplicationIdentityCard
        candidateName="John Doe"
        candidateEmail="john@example.com"
        candidateId={CANDIDATE_ID}
        applicationId={APPLICATION_ID}
        jobTitle="Senior Backend Engineer"
        jobId="job-1"
        applicationStatus="shortlisted"
        interviewIds={[{ interviewId: "int-1" }]}
      />,
    );

    expect(screen.getByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("john@example.com")).toBeInTheDocument();
    expect(screen.getByText("Senior Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Shortlisted")).toBeInTheDocument();

    for (const label of [
      "Candidate ID",
      "Application ID",
      "Job ID",
      "Interview ID",
    ]) {
      expect(screen.getByText(label, { selector: "label" })).toBeInTheDocument();
    }

    // Each identifier is explained, so "candidate" and "application" cannot be
    // confused for one another.
    expect(
      screen.getByText("Identifies the person, across all their applications."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Identifies this application, for this job."),
    ).toBeInTheDocument();
  });

  it("prefers the server's status wording over a locally derived one", () => {
    render(
      <ApplicationIdentityCard
        candidateName="John Doe"
        candidateId={CANDIDATE_ID}
        applicationId={APPLICATION_ID}
        applicationStatus="interview_scheduled"
        statusLabel="Interview Scheduled"
      />,
    );
    expect(screen.getByText("Interview Scheduled")).toBeInTheDocument();
  });

  it("omits the interview identifier when the application has no interview", () => {
    render(
      <ApplicationIdentityCard
        candidateName="John Doe"
        candidateId={CANDIDATE_ID}
        applicationId={APPLICATION_ID}
      />,
    );
    expect(screen.queryByText("Interview ID")).not.toBeInTheDocument();
  });
});
