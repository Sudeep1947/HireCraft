export type RoleName = "super_admin" | "organization_admin" | "hr_manager" | "hr" | "recruiter" | "candidate" | "admin";

export interface OrganizationMembershipBrief {
  id: string;
  organization_id: string;
  organization_name: string;
  role: string;
  status: string;
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  roles: RoleName[];
  organization_memberships?: OrganizationMembershipBrief[];
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface RegisterRequest {
  full_name: string;
  email: string;
  password: string;
}

export interface TokenUserInfo {
  id: string;
  full_name: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  roles: RoleName[];
  organization_memberships?: OrganizationMembershipBrief[];
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user?: TokenUserInfo;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface Invitation {
  id: string;
  email: string;
  role: string;
  status: string;
  organization_id: string;
  expires_at: string | null;
  created_at: string;
  accepted_at: string | null;
  email_status?: string;
  accept_url?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description?: string;
  official_email?: string;
  domain?: string;
  logo_url?: string;
  industry?: string;
  website?: string;
  location?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface OrganizationMembership {
  id: string;
  user_id: string;
  organization_id: string;
  role: string;
  status: string;
  invited_by_id?: string;
  joined_at?: string;
  created_at: string;
  user?: {
    id: string;
    full_name: string;
    email: string;
  };
}