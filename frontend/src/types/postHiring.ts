export type OfferStatus =
  | 'draft'
  | 'pending_approval'
  | 'sent'
  | 'viewed'
  | 'accepted'
  | 'declined'
  | 'expired'
  | 'withdrawn';

export type DocumentVerificationStatus =
  | 'not_submitted'
  | 'submitted'
  | 'under_review'
  | 'verified'
  | 'rejected'
  | 'resubmission_required';

export type EmploymentStatus = 'onboarding' | 'active' | 'on_leave' | 'terminated';

export type OnboardingStatus = 'not_started' | 'in_progress' | 'completed';

export interface JobOffer {
  id: string;
  application_id: string;
  candidate_id: string;
  candidate_name?: string;
  candidate_email?: string;
  job_id: string;
  job_title?: string;
  organization_id: string;
  organization_name?: string;
  created_by_id?: string;
  created_by_name?: string;
  designation: string;
  department: string;
  employment_type: string;
  offered_salary: number;
  currency: string;
  work_location: string;
  reporting_manager?: string;
  joining_date: string;
  probation_period_months: number;
  benefits_summary?: string;
  additional_terms?: string;
  offer_expiry_date: string;
  hr_remarks?: string;
  status: OfferStatus;
  sent_at?: string;
  viewed_at?: string;
  responded_at?: string;
  decline_reason?: string;
  candidate_notes?: string;
  offer_reference_no?: string;
  application_reference?: string;
  work_arrangement?: string;
  base_salary?: number;
  variable_compensation?: number;
  allowances?: number;
  variable_percentage?: number;
  candidate_phone?: string;
  candidate_avatar_url?: string;
  candidate_location?: string;
  created_at: string;
  updated_at: string;
}

export interface CandidateDocument {
  id: string;
  application_id: string;
  candidate_id: string;
  candidate_name?: string;
  candidate_email?: string;
  organization_id: string;
  document_type: string;
  document_title: string;
  file_url?: string;
  file_name?: string;
  file_size?: number;
  mime_type?: string;
  status: DocumentVerificationStatus;
  submitted_at?: string;
  verified_at?: string;
  verified_by_id?: string;
  verified_by_name?: string;
  hr_remarks?: string;
  created_at: string;
  updated_at: string;
}

export interface OnboardingTask {
  id: string;
  employee_id: string;
  organization_id: string;
  title: string;
  description?: string;
  category: string;
  assigned_to_role: string;
  deadline?: string;
  status?: string;
  instructions?: string;
  submission_notes?: string;
  attachment_url?: string;
  is_completed: boolean;
  completed_at?: string;
  completed_by_id?: string;
  hr_remarks?: string;
  created_at: string;
  updated_at: string;
}

export interface Employee {
  id: string;
  employee_id: string;
  user_id: string;
  user_name?: string;
  user_email?: string;
  application_id?: string;
  organization_id: string;
  organization_name?: string;
  designation: string;
  department: string;
  employment_type: string;
  work_location: string;
  reporting_manager?: string;
  joining_date: string;
  employment_status: EmploymentStatus;
  onboarding_status: OnboardingStatus;
  onboarding_completed_at?: string;
  profile_picture_url?: string;
  joining_status?: string;
  joining_confirmed_at?: string;
  joining_remarks?: string;
  checklist_template?: string;
  onboarding_deadline?: string;
  activated_at?: string;
  total_tasks: number;
  completed_tasks: number;
  onboarding_progress_percent: number;
  tasks: OnboardingTask[];
  created_at: string;
  updated_at: string;
}

export interface UpcomingJoining {
  employee_id?: string;
  candidate_name: string;
  candidate_email: string;
  designation: string;
  department: string;
  joining_date: string;
  status: string;
  avatar_url?: string;
}

export interface RecentHiringActivity {
  id: string;
  title: string;
  description: string;
  activity_type: string;
  timestamp: string;
  badge_variant: string;
}

export interface PostHiringStats {
  total_selected_candidates: number;
  offers_created: number;
  offers_sent: number;
  offers_viewed: number;
  offers_pending: number;
  offers_accepted: number;
  offers_declined: number;
  documents_submitted: number;
  documents_pending_verification: number;
  documents_verified: number;
  documents_requiring_resubmission: number;
  employees_onboarding: number;
  onboarding_tasks_pending: number;
  onboarding_completion_rate: number;
  active_employees: number;
  upcoming_joinings: UpcomingJoining[];
  recent_activities: RecentHiringActivity[];
}

export interface RecruiterPostHiringCandidateItem {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  job_id: string;
  job_title: string;
  department: string;
  hr_hiring_decision: string;
  offer_id?: string | null;
  offer_status?: string | null;
  offer_sent_at?: string | null;
  offer_accepted_at?: string | null;
  joining_date?: string | null;
  document_submission_status: string;
  documents_submitted: number;
  documents_verified: number;
  documents_total: number;
  onboarding_status: string;
  onboarding_progress_percent: number;
  employee_status: string;
  employee_id_code?: string | null;
  updated_at?: string | null;
}

export interface PostHiringTimelineEvent {
  id: string;
  timestamp: string;
  event_type: string;
  title: string;
  description: string;
  actor_name: string;
  actor_role: string;
  status: string;
  action_link?: string | null;
}

export interface ApprovedCandidateSummary {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  job_id: string;
  job_title: string;
  department: string;
  application_status: string;
  has_offer: boolean;
  offer_id?: string;
  offer_status?: OfferStatus;
  recruiter_score?: number;
  hr_score?: number;
  decision?: string;
}

export interface JobOfferCreatePayload {
  application_id: string;
  designation: string;
  department: string;
  employment_type: string;
  offered_salary: number;
  currency: string;
  work_location: string;
  reporting_manager?: string;
  joining_date: string;
  probation_period_months: number;
  benefits_summary?: string;
  additional_terms?: string;
  offer_expiry_date: string;
  hr_remarks?: string;
  offer_reference_no?: string;
  work_arrangement?: string;
  base_salary?: number;
  variable_compensation?: number;
  allowances?: number;
  send_immediately: boolean;
}

export interface EmployeeCreatePayload {
  candidate_id: string;
  application_id?: string;
  designation: string;
  department: string;
  employment_type: string;
  work_location: string;
  reporting_manager?: string;
  joining_date: string;
  profile_picture_url?: string;
  checklist_template?: string;
  onboarding_deadline?: string;
}

export interface JoiningConfirmPayload {
  joining_status: 'confirmed' | 'no_show' | 'cancelled';
  joining_date?: string;
  remarks?: string;
}

export interface CandidateTaskSubmitPayload {
  submission_notes?: string;
  attachment_url?: string;
}

export interface TaskReviewPayload {
  status: 'completed' | 'rejected';
  hr_remarks?: string;
}
