import apiClient from "./client";
import type {
  ApplicationAssessmentAssignRequest,
  ApplicationAssessmentAssignResult,
  ApplicationAssessmentEvidence,
  ApplicationAssessmentOptions,
  CandidateApplicationAssessmentView,
} from "../types/applicationAssessment";

/**
 * Phase 12: run an existing assessment from an application.
 *
 * Every call is keyed by application id. The job, candidate and organization are
 * derived server-side from that application, so none of these methods accept
 * them: a UI that could pass a candidate id would suggest a recruiter can aim an
 * assessment at someone other than the applicant.
 *
 * This is a thin front door onto the platform's existing assessment engine. It
 * creates no new engine, question bank, grading path or notification system — it
 * only exposes the application-driven entry points, so the recruiter reaches the
 * assessment from the application and the candidate takes it through the same
 * `/candidate/assessments/take/:assessmentId` experience as before.
 */
export const applicationAssessmentApi = {
  /**
   * Server-authoritative assignment affordances for one application: the catalog
   * this recruiter may assign from, whether an assignment is possible at all, and
   * why not. The panel renders this rather than re-deriving eligibility, so a
   * control it offers is one the API accepts.
   */
  getOptions: async (applicationId: string): Promise<ApplicationAssessmentOptions> => {
    const res = await apiClient.get(
      `/assessments/applications/${applicationId}/assessment/options`,
    );
    return res.data;
  },

  /**
   * Assign an existing assessment to an application.
   *
   * Idempotent against a double-click or a retry: while an attempt for the same
   * assessment is still live, the server re-reads it and reports
   * `already_assigned` instead of creating a second open attempt.
   */
  assign: async (
    applicationId: string,
    data: ApplicationAssessmentAssignRequest,
  ): Promise<ApplicationAssessmentAssignResult> => {
    const res = await apiClient.post(
      `/assessments/applications/${applicationId}/assessment/assign`,
      data,
    );
    return res.data;
  },

  /**
   * Create a candidate-specific assessment and assign it in one action.
   */
  createAndAssign: async (
    applicationId: string,
    data: import("../types/applicationAssessment").ApplicationAssessmentCreateRequest,
  ): Promise<import("../types/applicationAssessment").ApplicationAssessmentCreateResult> => {
    const res = await apiClient.post(
      `/assessments/applications/${applicationId}/assessment/create-and-assign`,
      data,
    );
    return res.data;
  },

  /** All assessment evidence recorded against one application. Staff-only. */
  getEvidence: async (applicationId: string): Promise<ApplicationAssessmentEvidence> => {
    const res = await apiClient.get(
      `/assessments/applications/${applicationId}/assessment/evidence`,
    );
    return res.data;
  },

  /**
   * The candidate's own view of the assessment on their application.
   *
   * Candidate-scoped and allowlisted by the server: no recruiter identity, notes,
   * protected attributes or internal grading labels. "No such application" and
   * "not your application" both answer 404, so ids cannot be probed.
   */
  getMyApplicationAssessment: async (
    applicationId: string,
  ): Promise<CandidateApplicationAssessmentView> => {
    const res = await apiClient.get(
      `/assessments/applications/${applicationId}/assessment`,
    );
    return res.data;
  },
};

export default applicationAssessmentApi;
