import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RootRoute } from "./components/routing/RootRoute";
import { AppLayout } from "./components/layout/AppLayout";
import { AuthProvider } from "./contexts/AuthContext";
import { ToastProvider } from "./contexts/ToastContext";
import type { RoleName } from "./types/auth";

// Auth pages
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { AccessDenied } from "./pages/AccessDenied";
import { InviteAccept } from "./pages/InviteAccept";
import { OAuthCallback } from "./pages/OAuthCallback";

// Shared
import { Dashboard } from "./pages/Dashboard";
import { TeamManagement } from "./pages/TeamManagement";

// Candidate pages
import { CandidateDashboard } from "./pages/candidate/Dashboard";
import { CandidateProfile } from "./pages/candidate/Profile";
import { CandidateEducation } from "./pages/candidate/Education";
import { CandidateExperience } from "./pages/candidate/Experience";
import { CandidateSkills } from "./pages/candidate/Skills";
import { CandidateProjects } from "./pages/candidate/Projects";
import { CandidateCertifications } from "./pages/candidate/Certifications";
import { CandidateLanguages } from "./pages/candidate/Languages";
import { CandidateNotifications } from "./pages/candidate/Notifications";
import { CandidateSettings } from "./pages/candidate/Settings";
import { ResumeDashboard } from "./pages/candidate/ResumeDashboard";
import { ResumeDetail } from "./pages/candidate/ResumeDetail";
import { ResumeUpload } from "./pages/candidate/ResumeUpload";
import { CandidateIntelligence } from "./pages/candidate/CandidateIntelligence";
import { ProfileSync } from "./pages/candidate/ProfileSync";
import { ResumeHistory } from "./pages/candidate/ResumeHistory";
import { ResumeIntelligence } from "./pages/candidate/ResumeIntelligence";
import { JobPortal } from "./pages/candidate/JobPortal";
import { CandidateJobDetail } from "./pages/candidate/CandidateJobDetail";
import { MyApplications } from "./pages/candidate/MyApplications";
import { CandidateApplicationDetail } from "./pages/candidate/ApplicationDetail";
import { CandidateApplicationExplanationPage } from "./pages/candidate/ApplicationExplanation";
import { SavedJobs } from "./pages/candidate/SavedJobs";
import { CandidateJobMatchReport } from "./pages/candidate/JobMatchReport";
import { Skill2JobHome } from "./pages/Skill2Job/Skill2JobHome";
import Skill2JobLayout from "./pages/Skill2Job/Skill2JobLayout";
import OverviewPage from "./pages/Skill2Job/pages/OverviewPage";
import ProfilePage from "./pages/Skill2Job/pages/ProfilePage";
import JobsPage from "./pages/Skill2Job/pages/JobsPage";
import JobDetailPage from "./pages/Skill2Job/pages/JobDetailPage";
import SkillGapsPage from "./pages/Skill2Job/pages/SkillGapsPage";
import SkillGraphPage from "./pages/Skill2Job/pages/SkillGraphPage";
import OpportunitiesPage from "./pages/Skill2Job/pages/OpportunitiesPage";
import LearningPage from "./pages/Skill2Job/pages/LearningPage";
import TimeToReadyPage from "./pages/Skill2Job/pages/TimeToReadyPage";
import SkillProofPage from "./pages/Skill2Job/pages/SkillProofPage";

// Recruiter pages
import { RecruiterDashboard } from "./pages/recruiter/RecruiterDashboard";
import { RecruiterJobDashboard } from "./pages/recruiter/JobDashboard";
import { RecruiterJobCreate } from "./pages/recruiter/JobCreate";
import { RecruiterJobDetail } from "./pages/recruiter/JobDetail";
import { RecruiterJobEdit } from "./pages/recruiter/JobEdit";
import { RecruiterJobApplicants } from "./pages/recruiter/JobApplicants";
import { RecruiterScreeningDetail } from "./pages/recruiter/ScreeningDetail";
import { RecruiterApplicationExplanationPage } from "./pages/recruiter/ApplicationExplanation";
import { SimulationDashboard } from "./pages/recruiter/SimulationDashboard";
import { CreateSimulation } from "./pages/recruiter/CreateSimulation";
import { SimulationDetails } from "./pages/recruiter/SimulationDetails";
import { SimulationResults } from "./pages/recruiter/SimulationResults";
import { SimulationRankingImpact } from "./pages/recruiter/SimulationRankingImpact";
import { SimulationRequirementImpact } from "./pages/recruiter/SimulationRequirementImpact";
import { SimulationThresholdShortlist } from "./pages/recruiter/SimulationThresholdShortlist";
import { SimulationFairnessImpact } from "./pages/recruiter/SimulationFairnessImpact";
import { SimulationExplainabilityImpact } from "./pages/recruiter/SimulationExplainabilityImpact";
import { SimulationSkillImpact } from "./pages/recruiter/SimulationSkillImpact";
import { SimulationComparison } from "./pages/recruiter/SimulationComparison";
import { SimulationAssistant } from "./pages/recruiter/SimulationAssistant";
import { SandboxDashboard } from "./pages/recruiter/SandboxDashboard";
import SimulationReportsList from "./pages/recruiter/SimulationReportsList";
import SimulationReportDetail from "./pages/recruiter/SimulationReportDetail";
import { ResearchDashboard } from "./pages/recruiter/ResearchDashboard";
import { CreateExperiment } from "./pages/recruiter/CreateExperiment";
import { ExperimentDetail } from "./pages/recruiter/ExperimentDetail";
import { CandidateFit } from "./pages/recruiter/CandidateFit";
import { CandidateIntelligence as RecruiterCandidateIntelligence } from "./pages/recruiter/CandidateIntelligence";
import { RecruiterNotifications } from "./pages/recruiter/Notifications";
import { RecruiterCandidateRanking } from "./pages/recruiter/CandidateRanking";
import { CandidateComparison } from "./pages/recruiter/CandidateComparison";
import { RecruiterAIInsights } from "./pages/recruiter/AIInsights";
import { AISearchPage } from "./pages/recruiter/AISearch";
import { TopCandidatesPage } from "./pages/recruiter/TopCandidates";
import { CandidateAIDashboard } from "./pages/candidate/CandidateAIDashboard";
import { CandidateExplainability } from "./pages/candidate/CandidateExplainability";
import { CandidateFairness } from "./pages/candidate/CandidateFairness";
import { ExplainabilityDashboard } from "./pages/recruiter/Explainability";
import { RecruiterFairnessDashboard } from "./pages/recruiter/FairnessDashboard";

// AI Agent pages
import { AIChat } from "./pages/agent/AIChat";

// Interview pages
import { MockInterview } from "./pages/interview/MockInterview";
import { InterviewHistory } from "./pages/interview/InterviewHistory";
import { InterviewDetailPage as CandidateInterviewDetail } from "./pages/interview/InterviewDetail";
import { InterviewWorkspace } from "./pages/interview/InterviewWorkspace";
import { InterviewDetailPage as RecruiterInterviewDetail } from "./pages/interview/InterviewDetail";
import { InterviewAnalyticsPage } from "./pages/interview/InterviewAnalytics";
import { InterviewSchedule } from "./pages/interview/InterviewSchedule";
import { InterviewVideoPage } from "./pages/interview/InterviewVideoPage";

// Assessment platform pages
import { AssessmentBuilder } from "./pages/assessments/AssessmentBuilder";
import { AssessmentLibrary } from "./pages/assessments/AssessmentLibrary";
import { TakeAssessment } from "./pages/assessments/TakeAssessment";
import { MyAssessments } from "./pages/assessments/MyAssessments";
import { AssessmentResult } from "./pages/assessments/AssessmentResult";
import { RecruiterAssessmentAnalytics } from "./pages/assessments/RecruiterAnalytics";

// Analytics pages
import { CandidateAnalytics } from "./pages/analytics/CandidateAnalytics";
import { RecruiterAnalytics } from "./pages/analytics/RecruiterAnalyticsPage";
import { HRAnalyticsPage } from "./pages/analytics/HRAnalyticsPage";
import { AdminAnalyticsPage } from "./pages/analytics/AdminAnalyticsPage";
import { ExecutiveKPIsPage } from "./pages/analytics/ExecutiveKPIsPage";
import { PredictiveAnalyticsPage } from "./pages/analytics/PredictiveAnalyticsPage";

// HR pages
import { HROversightDashboard } from "./pages/hr/HROversightDashboard";
import { HRJobsPage } from "./pages/hr/HRJobsPage";
import { HRJobApplicationsPage } from "./pages/hr/HRJobApplicationsPage";
import { HRApplicationDetailPage } from "./pages/hr/HRApplicationDetailPage";
import { HRFairnessDashboard } from "./pages/hr/HRFairnessDashboard";
import { HRRecruitersPage } from "./pages/hr/HRRecruitersPage";
import { HRRecruiterDetailPage } from "./pages/hr/HRRecruiterDetailPage";
import { HRAttentionPage } from "./pages/hr/HRAttentionPage";
import { HRQualityPage } from "./pages/hr/HRQualityPage";
import { HRStagePage } from "./pages/hr/HRStagePage";
import HROffersPage from "./pages/hr/HROffersPage";
import HRDocumentsPage from "./pages/hr/HRDocumentsPage";
import HROnboardingPage from "./pages/hr/HROnboardingPage";
import HREmployeesPage from "./pages/hr/HREmployeesPage";
import CandidateOffersOnboarding from "./pages/candidate/CandidateOffersOnboarding";

// Admin pages
import { AdminDashboard } from "./pages/admin/AdminDashboard";
import { UserManagement } from "./pages/admin/UserManagement";
import { AuditLogs } from "./pages/admin/AuditLogs";
import { DemoCenter } from "./pages/admin/DemoCenter";
import { Skill2JobDiagnostics } from "./pages/admin/Skill2JobDiagnostics";
import { AdminAccessRequests } from "./pages/admin/AdminAccessRequests";

// Access request pages (public)
import { RequestAccess } from "./pages/RequestAccess";
import { VerifyAccessEmail } from "./pages/VerifyAccessEmail";
import { AccessRequestPending } from "./pages/AccessRequestPending";
import { ActivateAccount } from "./pages/ActivateAccount";

const SUPER_ADMIN: RoleName[] = ["super_admin", "admin"];
const ORG_ADMIN: RoleName[] = ["organization_admin", "super_admin", "admin"];
const HR_MANAGER: RoleName[] = ["hr", "hr_manager", "organization_admin", "admin", "super_admin"];
const RECRUITER: RoleName[] = ["hr", "hr_manager", "recruiter", "organization_admin", "admin", "super_admin"];
const CANDIDATE: RoleName[] = ["candidate"];
const ALL_AUTH: RoleName[] = ["admin", "super_admin", "organization_admin", "hr", "hr_manager", "recruiter", "candidate"];

export function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <ToastProvider>
          <Routes>
            {/* Public entry: landing page for visitors, role dashboard for authenticated users */}
            <Route path="/" element={<RootRoute />} />
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback/:provider" element={<OAuthCallback />} />
            <Route path="/register" element={<Register />} />
            <Route path="/access-denied" element={<AccessDenied />} />
            {/* Canonical invitation acceptance route (matches email CTA /invite/{token}) */}
            <Route path="/invite/:token" element={<InviteAccept />} />
            {/* Legacy alias kept for older links */}
            <Route path="/invite/accept/:token" element={<InviteAccept />} />

            {/* Access request flow (public, no auth required) */}
            <Route path="/request-access" element={<RequestAccess />} />
            <Route path="/verify-email" element={<VerifyAccessEmail />} />
            <Route path="/access-requests/:requestId" element={<AccessRequestPending />} />
            <Route path="/activate" element={<ActivateAccount />} />

            <Route element={<AppLayout />}>
              {/* Global dashboard redirect */}
              <Route path="/dashboard" element={<ProtectedRoute roles={ALL_AUTH}><Dashboard /></ProtectedRoute>} />

              {/* The live interview room: one shared route for both sides of
                  the same interview. The page adds no access rule of its own —
                  it renders whatever the server's room endpoint says, and the
                  signaling socket re-authorizes, so a candidate can never
                  enter a room they are not part of. */}
              <Route path="/interviews/:id/room" element={<ProtectedRoute roles={ALL_AUTH}><InterviewVideoPage /></ProtectedRoute>} />
              <Route path="/interview/:id/room" element={<ProtectedRoute roles={ALL_AUTH}><InterviewVideoPage /></ProtectedRoute>} />

              {/* ─── Candidate Routes ────────────────────────── */}
              <Route path="/candidate/dashboard" element={<ProtectedRoute roles={CANDIDATE}><CandidateDashboard /></ProtectedRoute>} />
        <Route path="/candidate/offers-onboarding" element={<ProtectedRoute roles={CANDIDATE}><CandidateOffersOnboarding /></ProtectedRoute>} />
              <Route path="/candidate/profile" element={<ProtectedRoute roles={CANDIDATE}><CandidateProfile /></ProtectedRoute>} />
              <Route path="/candidate/education" element={<ProtectedRoute roles={CANDIDATE}><CandidateEducation /></ProtectedRoute>} />
              <Route path="/candidate/experience" element={<ProtectedRoute roles={CANDIDATE}><CandidateExperience /></ProtectedRoute>} />
              <Route path="/candidate/skills" element={<ProtectedRoute roles={CANDIDATE}><CandidateSkills /></ProtectedRoute>} />
              <Route path="/candidate/projects" element={<ProtectedRoute roles={CANDIDATE}><CandidateProjects /></ProtectedRoute>} />
              <Route path="/candidate/certifications" element={<ProtectedRoute roles={CANDIDATE}><CandidateCertifications /></ProtectedRoute>} />
              <Route path="/candidate/languages" element={<ProtectedRoute roles={CANDIDATE}><CandidateLanguages /></ProtectedRoute>} />
              <Route path="/candidate/notifications" element={<ProtectedRoute roles={CANDIDATE}><CandidateNotifications /></ProtectedRoute>} />
              <Route path="/candidate/settings" element={<ProtectedRoute roles={CANDIDATE}><CandidateSettings /></ProtectedRoute>} />
              <Route path="/candidate/resume" element={<ProtectedRoute roles={CANDIDATE}><ResumeDashboard /></ProtectedRoute>} />
              <Route path="/candidate/resume/upload" element={<ProtectedRoute roles={CANDIDATE}><ResumeUpload /></ProtectedRoute>} />
              <Route path="/candidate/resume/:id" element={<ProtectedRoute roles={CANDIDATE}><ResumeDetail /></ProtectedRoute>} />
              <Route path="/candidate/resume/:id/sync" element={<ProtectedRoute roles={CANDIDATE}><ProfileSync /></ProtectedRoute>} />
              <Route path="/candidate/resume/:id/intelligence" element={<ProtectedRoute roles={CANDIDATE}><ResumeIntelligence /></ProtectedRoute>} />
              <Route path="/candidate/resume/history" element={<ProtectedRoute roles={CANDIDATE}><ResumeHistory /></ProtectedRoute>} />
              <Route path="/candidate/intelligence" element={<ProtectedRoute roles={CANDIDATE}><CandidateIntelligence /></ProtectedRoute>} />
              <Route path="/candidate/ai-dashboard" element={<ProtectedRoute roles={CANDIDATE}><CandidateAIDashboard /></ProtectedRoute>} />
              <Route path="/candidate/explainability" element={<ProtectedRoute roles={CANDIDATE}><CandidateExplainability /></ProtectedRoute>} />
              <Route path="/candidate/fairness" element={<ProtectedRoute roles={CANDIDATE}><CandidateFairness /></ProtectedRoute>} />
              <Route path="/candidate/jobs" element={<ProtectedRoute roles={CANDIDATE}><JobPortal /></ProtectedRoute>} />
              <Route path="/candidate/jobs/:id" element={<ProtectedRoute roles={CANDIDATE}><CandidateJobDetail /></ProtectedRoute>} />
              <Route path="/candidate/jobs/:id/match" element={<ProtectedRoute roles={CANDIDATE}><CandidateJobMatchReport /></ProtectedRoute>} />
              <Route path="/candidate/applications" element={<ProtectedRoute roles={CANDIDATE}><MyApplications /></ProtectedRoute>} />
              <Route path="/candidate/applications/:applicationId" element={<ProtectedRoute roles={CANDIDATE}><CandidateApplicationDetail /></ProtectedRoute>} />
      <Route path="/candidate/applications/:applicationId/explanation" element={<ProtectedRoute roles={CANDIDATE}><CandidateApplicationExplanationPage /></ProtectedRoute>} />
              <Route path="/candidate/saved-jobs" element={<ProtectedRoute roles={CANDIDATE}><SavedJobs /></ProtectedRoute>} />

              {/* ─── Skill2Job Routes (Candidate Career Intelligence) ── */}
              <Route path="/candidate/skill2job" element={<ProtectedRoute roles={CANDIDATE}><Skill2JobHome /></ProtectedRoute>} />
              <Route path="/skill2job" element={<ProtectedRoute roles={CANDIDATE}><Skill2JobLayout /></ProtectedRoute>}>
                <Route index element={<OverviewPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="jobs" element={<JobsPage />} />
                <Route path="jobs/:id" element={<JobDetailPage />} />
                <Route path="skill-gaps" element={<SkillGapsPage />} />
                <Route path="skill-graph" element={<SkillGraphPage />} />
                <Route path="opportunities" element={<OpportunitiesPage />} />
                <Route path="learning" element={<LearningPage />} />
                <Route path="time-to-ready" element={<TimeToReadyPage />} />
                <Route path="skill-proof" element={<SkillProofPage />} />
              </Route>

              {/* ─── Candidate Interview Routes ──────────────── */}
              <Route path="/candidate/mock-interview" element={<ProtectedRoute roles={CANDIDATE}><MockInterview /></ProtectedRoute>} />
              <Route path="/candidate/interview-history" element={<ProtectedRoute roles={CANDIDATE}><InterviewHistory /></ProtectedRoute>} />
              <Route path="/candidate/interviews/:id" element={<ProtectedRoute roles={CANDIDATE}><CandidateInterviewDetail /></ProtectedRoute>} />

              {/* ─── Candidate Assessment Routes ─────────────── */}
              <Route path="/candidate/assessments" element={<ProtectedRoute roles={CANDIDATE}><MyAssessments /></ProtectedRoute>} />
              <Route path="/candidate/assessments/take/:assessmentId" element={<ProtectedRoute roles={CANDIDATE}><TakeAssessment /></ProtectedRoute>} />
              <Route path="/candidate/assessments/results/:attemptId" element={<ProtectedRoute roles={CANDIDATE}><AssessmentResult /></ProtectedRoute>} />

              {/* ─── Candidate Analytics Routes ─────────────── */}
              <Route path="/candidate/analytics" element={<ProtectedRoute roles={CANDIDATE}><CandidateAnalytics /></ProtectedRoute>} />
              <Route path="/candidate/insights" element={<ProtectedRoute roles={CANDIDATE}><CandidateAnalytics /></ProtectedRoute>} />

              {/* ─── Recruiter Routes ────────────────────────── */}
              <Route path="/recruiter/dashboard" element={<ProtectedRoute roles={RECRUITER}><RecruiterDashboard /></ProtectedRoute>} />
              <Route path="/recruiter/jobs" element={<ProtectedRoute roles={RECRUITER}><RecruiterJobDashboard /></ProtectedRoute>} />
              <Route path="/recruiter/jobs/create" element={<ProtectedRoute roles={RECRUITER}><RecruiterJobCreate /></ProtectedRoute>} />
              <Route path="/recruiter/jobs/:id" element={<ProtectedRoute roles={RECRUITER}><RecruiterJobDetail /></ProtectedRoute>} />
              <Route path="/recruiter/jobs/:id/edit" element={<ProtectedRoute roles={RECRUITER}><RecruiterJobEdit /></ProtectedRoute>} />
              <Route path="/recruiter/jobs/:id/applicants" element={<ProtectedRoute roles={RECRUITER}><RecruiterJobApplicants /></ProtectedRoute>} />
      <Route path="/recruiter/jobs/:jobId/applicants/:applicationId/screening" element={<ProtectedRoute roles={RECRUITER}><RecruiterScreeningDetail /></ProtectedRoute>} />
      <Route path="/recruiter/jobs/:jobId/applicants/:applicationId/explanation" element={<ProtectedRoute roles={RECRUITER}><RecruiterApplicationExplanationPage /></ProtectedRoute>} />
              {/* Phase 12: the recruiter's detailed view of an attempt's result,
                  reached from the application assessment panel. Reuses the existing
                  AssessmentResult component and the existing result API — the
                  candidate route above stays candidate-only. */}
              <Route path="/recruiter/assessments/results/:attemptId" element={<ProtectedRoute roles={RECRUITER}><AssessmentResult audience="staff" /></ProtectedRoute>} />
              <Route path="/recruiter/jobs/:id/candidates/:candidateId/fit" element={<ProtectedRoute roles={RECRUITER}><CandidateFit /></ProtectedRoute>} />
              <Route path="/recruiter/jobs/:id/candidates/:candidateId/intelligence" element={<ProtectedRoute roles={RECRUITER}><RecruiterCandidateIntelligence /></ProtectedRoute>} />
              <Route path="/recruiter/candidates/:candidateId/intelligence" element={<ProtectedRoute roles={RECRUITER}><RecruiterCandidateIntelligence /></ProtectedRoute>} />
              <Route path="/recruiter/jobs/:id/rankings" element={<ProtectedRoute roles={RECRUITER}><RecruiterCandidateRanking /></ProtectedRoute>} />
              <Route path="/recruiter/jobs/:id/compare" element={<ProtectedRoute roles={RECRUITER}><CandidateComparison /></ProtectedRoute>} />
              <Route path="/recruiter/ai-insights" element={<ProtectedRoute roles={RECRUITER}><RecruiterAIInsights /></ProtectedRoute>} />
              <Route path="/recruiter/explainability" element={<ProtectedRoute roles={RECRUITER}><ExplainabilityDashboard /></ProtectedRoute>} />
              <Route path="/recruiter/fairness" element={<ProtectedRoute roles={RECRUITER}><RecruiterFairnessDashboard /></ProtectedRoute>} />
              <Route path="/recruiter/ai-search" element={<ProtectedRoute roles={RECRUITER}><AISearchPage /></ProtectedRoute>} />
              <Route path="/recruiter/top-candidates" element={<ProtectedRoute roles={RECRUITER}><TopCandidatesPage /></ProtectedRoute>} />
              <Route path="/recruiter/rankings" element={<ProtectedRoute roles={RECRUITER}><RecruiterCandidateRanking /></ProtectedRoute>} />
              <Route path="/recruiter/notifications" element={<ProtectedRoute roles={RECRUITER}><RecruiterNotifications /></ProtectedRoute>} />

              {/* ─── Simulation Intelligence Routes ─────────── */}
              <Route path="/recruiter/simulations" element={<ProtectedRoute roles={RECRUITER}><SimulationDashboard /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/create" element={<ProtectedRoute roles={RECRUITER}><CreateSimulation /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/compare" element={<ProtectedRoute roles={RECRUITER}><SimulationComparison /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/assistant" element={<ProtectedRoute roles={RECRUITER}><SimulationAssistant /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/sandbox" element={<ProtectedRoute roles={RECRUITER}><SandboxDashboard /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/:simulationId" element={<ProtectedRoute roles={RECRUITER}><SimulationDetails /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/:simulationId/results" element={<ProtectedRoute roles={RECRUITER}><SimulationResults /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/:simulationId/impact" element={<ProtectedRoute roles={RECRUITER}><SimulationRankingImpact /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/:simulationId/requirement-impact" element={<ProtectedRoute roles={RECRUITER}><SimulationRequirementImpact /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/:simulationId/threshold-shortlist" element={<ProtectedRoute roles={RECRUITER}><SimulationThresholdShortlist /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/:simulationId/fairness-impact" element={<ProtectedRoute roles={RECRUITER}><SimulationFairnessImpact /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/:simulationId/explainability-impact" element={<ProtectedRoute roles={RECRUITER}><SimulationExplainabilityImpact /></ProtectedRoute>} />
              <Route path="/recruiter/simulations/:simulationId/skill-impact" element={<ProtectedRoute roles={RECRUITER}><SimulationSkillImpact /></ProtectedRoute>} />

              {/* ─── Simulation Report Routes ────────────────── */}
              <Route path="/simulations/reports" element={<ProtectedRoute roles={RECRUITER}><SimulationReportsList /></ProtectedRoute>} />
              <Route path="/simulations/reports/:reportId" element={<ProtectedRoute roles={RECRUITER}><SimulationReportDetail /></ProtectedRoute>} />

              {/* ─── Research Intelligence Routes ───────────── */}
              <Route path="/simulations/research" element={<ProtectedRoute roles={RECRUITER}><ResearchDashboard /></ProtectedRoute>} />
              <Route path="/simulations/research/new" element={<ProtectedRoute roles={RECRUITER}><CreateExperiment /></ProtectedRoute>} />
              <Route path="/simulations/research/:experimentId" element={<ProtectedRoute roles={RECRUITER}><ExperimentDetail /></ProtectedRoute>} />

              {/* ─── Recruiter Interview Routes ──────────────── */}
              <Route path="/recruiter/interviews" element={<ProtectedRoute roles={RECRUITER}><InterviewWorkspace /></ProtectedRoute>} />
              <Route path="/recruiter/interviews/schedule" element={<ProtectedRoute roles={RECRUITER}><InterviewSchedule /></ProtectedRoute>} />
              <Route path="/recruiter/interviews/:id" element={<ProtectedRoute roles={RECRUITER}><RecruiterInterviewDetail /></ProtectedRoute>} />
              <Route path="/recruiter/interview-analytics" element={<ProtectedRoute roles={RECRUITER}><InterviewAnalyticsPage /></ProtectedRoute>} />

              {/* ─── Assessment Platform Routes ──────────────── */}
              <Route path="/recruiter/assessments" element={<ProtectedRoute roles={RECRUITER}><AssessmentLibrary /></ProtectedRoute>} />
              <Route path="/recruiter/assessments/builder" element={<ProtectedRoute roles={RECRUITER}><AssessmentBuilder /></ProtectedRoute>} />
              <Route path="/recruiter/assessments/:assessmentId/analytics" element={<ProtectedRoute roles={RECRUITER}><RecruiterAssessmentAnalytics /></ProtectedRoute>} />

              {/* ─── Recruiter Analytics Routes ─────────────── */}
              <Route path="/recruiter/analytics" element={<ProtectedRoute roles={RECRUITER}><RecruiterAnalytics /></ProtectedRoute>} />
              <Route path="/recruiter/predictions" element={<ProtectedRoute roles={RECRUITER}><PredictiveAnalyticsPage /></ProtectedRoute>} />
              <Route path="/recruiter/insights" element={<ProtectedRoute roles={RECRUITER}><CandidateAnalytics /></ProtectedRoute>} />

              {/* ─── HR Routes ───────────────────────────────── */}
              {/* Revised Phase 14: the org-scoped oversight surface.
                  HR dashboard -> jobs -> applications -> application detail,
                  all read-only over the same JobApplication rows the recruiter
                  and candidate use. */}
              <Route path="/hr/dashboard" element={<ProtectedRoute roles={HR_MANAGER}><HROversightDashboard /></ProtectedRoute>} />
              <Route path="/hr/interviews" element={<ProtectedRoute roles={HR_MANAGER}><HROversightDashboard /></ProtectedRoute>} />
              <Route path="/hr/oversight" element={<ProtectedRoute roles={HR_MANAGER}><HROversightDashboard /></ProtectedRoute>} />
              <Route path="/hr/jobs" element={<ProtectedRoute roles={HR_MANAGER}><HRJobsPage /></ProtectedRoute>} />
              <Route path="/hr/jobs/:jobId/applications" element={<ProtectedRoute roles={HR_MANAGER}><HRJobApplicationsPage /></ProtectedRoute>} />
              <Route path="/hr/applications/:applicationId" element={<ProtectedRoute roles={HR_MANAGER}><HRApplicationDetailPage /></ProtectedRoute>} />
              <Route path="/hr/fairness" element={<ProtectedRoute roles={HR_MANAGER}><HRFairnessDashboard /></ProtectedRoute>} />
              <Route path="/hr/pipeline" element={<ProtectedRoute roles={HR_MANAGER}><HROversightDashboard /></ProtectedRoute>} />
        {/* Revised Phase 14: employer monitoring, deterministic attention rules,
            hiring-quality coverage, and a clickable funnel stage. Every route is
            read-only and guarded by the same HR role set as the rest of the
            oversight surface. */}
        <Route path="/hr/recruiters" element={<ProtectedRoute roles={HR_MANAGER}><HRRecruitersPage /></ProtectedRoute>} />
        <Route path="/hr/recruiters/:recruiterId" element={<ProtectedRoute roles={HR_MANAGER}><HRRecruiterDetailPage /></ProtectedRoute>} />
        <Route path="/hr/attention" element={<ProtectedRoute roles={HR_MANAGER}><HRAttentionPage /></ProtectedRoute>} />
        <Route path="/hr/quality" element={<ProtectedRoute roles={HR_MANAGER}><HRQualityPage /></ProtectedRoute>} />
        <Route path="/hr/pipeline/:status" element={<ProtectedRoute roles={HR_MANAGER}><HRStagePage /></ProtectedRoute>} />
        {/* Post-Hiring, Offer Management, Document Verification & Employee Onboarding */}
        <Route path="/hr/offers" element={<ProtectedRoute roles={HR_MANAGER}><HROffersPage /></ProtectedRoute>} />
        <Route path="/hr/documents" element={<ProtectedRoute roles={HR_MANAGER}><HRDocumentsPage /></ProtectedRoute>} />
        <Route path="/hr/onboarding" element={<ProtectedRoute roles={HR_MANAGER}><HROnboardingPage /></ProtectedRoute>} />
        <Route path="/hr/employees" element={<ProtectedRoute roles={HR_MANAGER}><HREmployeesPage /></ProtectedRoute>} />

              {/* ─── HR Interview Routes ─────────────────────── */}
              <Route path="/hr/interview-analytics" element={<ProtectedRoute roles={HR_MANAGER}><InterviewAnalyticsPage /></ProtectedRoute>} />

              {/* ─── HR Analytics Routes ─────────────────────── */}
              <Route path="/hr/analytics" element={<ProtectedRoute roles={HR_MANAGER}><HRAnalyticsPage /></ProtectedRoute>} />
              <Route path="/hr/executive" element={<ProtectedRoute roles={HR_MANAGER}><ExecutiveKPIsPage /></ProtectedRoute>} />
              <Route path="/hr/predictions" element={<ProtectedRoute roles={HR_MANAGER}><PredictiveAnalyticsPage /></ProtectedRoute>} />
              <Route path="/hr/insights" element={<ProtectedRoute roles={HR_MANAGER}><CandidateAnalytics /></ProtectedRoute>} />

              {/* ─── Admin Routes ────────────────────────────── */}
              <Route path="/admin/dashboard" element={<ProtectedRoute roles={SUPER_ADMIN}><AdminDashboard /></ProtectedRoute>} />
              <Route path="/admin/users" element={<ProtectedRoute roles={SUPER_ADMIN}><UserManagement /></ProtectedRoute>} />
              <Route path="/admin/audit-logs" element={<ProtectedRoute roles={SUPER_ADMIN}><AuditLogs /></ProtectedRoute>} />
              <Route path="/admin/demo" element={<ProtectedRoute roles={SUPER_ADMIN}><DemoCenter /></ProtectedRoute>} />
              <Route path="/admin/skill2job-diagnostics" element={<ProtectedRoute roles={SUPER_ADMIN}><Skill2JobDiagnostics /></ProtectedRoute>} />
              <Route path="/admin/access-requests" element={<ProtectedRoute roles={SUPER_ADMIN}><AdminAccessRequests /></ProtectedRoute>} />

              {/* ─── Admin Analytics Routes ──────────────────── */}
              <Route path="/admin/analytics" element={<ProtectedRoute roles={SUPER_ADMIN}><AdminAnalyticsPage /></ProtectedRoute>} />
              <Route path="/admin/executive" element={<ProtectedRoute roles={SUPER_ADMIN}><ExecutiveKPIsPage /></ProtectedRoute>} />
              <Route path="/admin/predictions" element={<ProtectedRoute roles={SUPER_ADMIN}><PredictiveAnalyticsPage /></ProtectedRoute>} />
              <Route path="/admin/insights" element={<ProtectedRoute roles={SUPER_ADMIN}><CandidateAnalytics /></ProtectedRoute>} />

              {/* ─── Organization Routes ──────────────────────── */}
              <Route path="/org/team" element={<ProtectedRoute roles={ORG_ADMIN}><TeamManagement /></ProtectedRoute>} />
              <Route path="/org/settings" element={<ProtectedRoute roles={ORG_ADMIN}><TeamManagement /></ProtectedRoute>} />

              {/* ─── AI Agent Routes (All Authenticated) ────── */}
              <Route path="/ai-chat" element={<ProtectedRoute roles={ALL_AUTH}><AIChat /></ProtectedRoute>} />
            </Route>

            {/* Unknown URLs: land on "/" — RootRoute then routes by auth state
                (dashboard for authenticated users, landing page otherwise). */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
