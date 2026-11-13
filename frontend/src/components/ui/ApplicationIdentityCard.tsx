/**
 * The identity block shown wherever a recruiter looks at one applicant.
 *
 * A UUID is only useful if you know what it identifies, so this card keeps the
 * four identifiers of the hiring workflow together and explicitly distinct:
 *
 * - **Candidate ID** identifies the person, across every application they have.
 * - **Application ID** identifies *this* application of theirs, for one job.
 * - **Job ID** identifies the role being recruited.
 * - **Interview ID** (where one exists) identifies a single interview.
 *
 * It also closes the discovery gap this screen used to have: an applicant
 * detail page that showed a name and a status but no identifiers, leaving a
 * recruiter who needed the candidate's UUID to go looking for it elsewhere.
 * Everything here is already loaded by the page that renders this card, so
 * nothing extra is fetched and the API contract is unchanged.
 *
 * Candidate name and email lead, and the identifiers sit below them: a UUID is
 * reference information, not the headline.
 */

import { IdentifierGrid } from "./IdentifierField";

export interface ApplicationIdentityCardProps {
  candidateName: string;
  candidateEmail?: string | null;
  /** `User.id` -- the canonical candidate identifier used across the workflow. */
  candidateId: string | null | undefined;
  /** `JobApplication.id`. */
  applicationId: string | null | undefined;
  jobTitle?: string | null;
  jobId?: string | null;
  applicationStatus?: string | null;
  /** Server-supplied wording for the status, preferred over a local guess. */
  statusLabel?: string | null;
  /** Interview ids recorded against this application, when the caller has them. */
  interviewIds?: Array<{ interviewId: string; scheduledAt?: string | null }>;
  title?: string;
  className?: string;
}

function humanizeStatus(status: string): string {
  return status.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export function ApplicationIdentityCard({
  candidateName,
  candidateEmail,
  candidateId,
  applicationId,
  jobTitle,
  jobId,
  applicationStatus,
  statusLabel,
  interviewIds,
  title = "Candidate information",
  className = "",
}: ApplicationIdentityCardProps) {
  const status = statusLabel ?? (applicationStatus ? humanizeStatus(applicationStatus) : null);

  return (
    <section
      className={`card p-4 ${className}`}
      data-testid="application-identity"
    >
      <h3 className="text-sm font-semibold text-ink">{title}</h3>

      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-sm font-medium text-ink">{candidateName}</span>
        {candidateEmail ? (
          <span className="text-sm text-ink-muted">{candidateEmail}</span>
        ) : null}
        {status ? (
          <span className="inline-flex items-center rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700 ring-1 ring-inset ring-primary-200/70">
            {status}
          </span>
        ) : null}
      </div>

      {jobTitle ? (
        <p className="mt-0.5 text-sm text-ink-muted">{jobTitle}</p>
      ) : null}

      <IdentifierGrid
        className="mt-3 border-t border-gray-200 pt-3"
        columns={2}
        items={[
          {
            label: "Candidate ID",
            value: candidateId,
            hint: "Identifies the person, across all their applications.",
          },
          {
            label: "Application ID",
            value: applicationId,
            hint: "Identifies this application, for this job.",
          },
          { label: "Job ID", value: jobId, hint: "Identifies the job." },
          ...(interviewIds ?? []).slice(0, 1).map((interview) => ({
            label: "Interview ID",
            value: interview.interviewId,
            hint: "Identifies the interview on this application.",
          })),
        ]}
      />
    </section>
  );
}

export default ApplicationIdentityCard;
