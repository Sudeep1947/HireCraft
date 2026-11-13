# Phase 1 — Secure Organization Creation

## 1. Initial findings

1. **Organization creation was available to any authenticated user.** `POST /api/v1/organizations` depended only on `get_current_user`, so a candidate, recruiter, HR manager, or organization admin could create a new tenant. An existing test even accepted `201` for a candidate.
2. **The request schema was too permissive.** `OrganizationCreate` used Pydantic's default `extra="ignore"`, so protected fields such as `id`, `status`, `role`, `created_by`, and `user_id` were silently discarded rather than rejected. Strings were not trimmed, and the slug pattern allowed leading, trailing, and doubled hyphens.
3. **The service did not defend itself.** `OrganizationService.create_organization` performed a loose regex check, did not validate the organization name, and did not normalize any input. The organization insert and creator-membership insert were separate flushes with no savepoint, and a concurrent duplicate slug could surface as a 500 instead of a 409.
4. **Audit logging was minimal.** The endpoint wrote only the raw slug and organization id, with no actor organization, actor roles, request correlation id, IP address, or user agent.
5. **The frontend had no organization-creation flow.** `TeamManagement.tsx` assumed the user already belonged to an organization.
6. **Tests encoded the old permissive behavior.** Candidate creation accepted `201` or `403`, and anonymous creation accepted `401` or `422`.

## 2. Files inspected

### Backend

- `backend/app/api/deps.py`
- `backend/app/api/v1/organizations.py`
- `backend/app/domain/schemas_organization.py`
- `backend/app/domain/models.py`
- `backend/app/domain/enums.py`
- `backend/app/core/permissions.py`
- `backend/app/core/config.py`
- `backend/app/core/middleware.py`
- `backend/app/services/organization_service.py`
- `backend/app/services/audit_service.py`
- `backend/app/repositories/organization.py`
- `backend/app/repositories/membership.py`
- `backend/app/repositories/base.py`
- `backend/app/db/session.py`
- `backend/tests/conftest.py`
- Existing organization, tenant, invitation, email, recruiter-invitation, and link-reachability tests.

### Frontend

- `frontend/src/pages/TeamManagement.tsx`
- `frontend/src/pages/admin/AdminDashboard.tsx`
- `frontend/src/api/auth.ts`
- `frontend/src/hooks/useAuth.ts`
- `frontend/src/utils/error.ts`
- `frontend/src/types/auth.ts`
- Existing UI components (`Button`, `Input`) and test setup.

## 3. Files modified

### Backend application

- `backend/app/api/deps.py`
  - Extracted `_load_user_from_authorization`.
  - Added `get_current_user_strict` so a missing `Authorization` header returns `401`, not FastAPI's `422`.
  - Added an opt-in `strict_auth` flag to `require_permission`; default behavior elsewhere is unchanged.
- `backend/app/api/v1/organizations.py`
  - Organization creation now requires `Permission.PLATFORM_ORG_MANAGE` with strict authentication.
  - Emits a complete audit record after successful creation.
- `backend/app/domain/schemas_organization.py`
  - `OrganizationCreate` rejects unknown/protected fields with `extra="forbid"`.
  - Text fields are trimmed before validation.
  - Slug pattern tightened to `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- `backend/app/services/organization_service.py`
  - Defense-in-depth normalization and validation for name and slug.
  - Explicit duplicate-slug conflict before insert.
  - Savepoint-atomic organization + creator-membership creation.
  - `IntegrityError` from the database unique constraint mapped to `409 Conflict`.

### Backend tests

- `backend/tests/test_secure_org_creation.py` (new)
- `backend/tests/test_phase1_tenant.py`
- `backend/tests/test_phase2_org.py`
- `backend/tests/test_phase4_invitation.py`

### Frontend

- `frontend/src/components/organization/CreateOrganizationCard.tsx` (new)
  - Shared creation form, validation, loading/success/error states, and duplicate-submit guard.
- `frontend/src/pages/admin/AdminDashboard.tsx`
  - Renders the creation card directly on the system admin dashboard.
  - Adds a "Manage organizations & teams" quick action to Team Management.
- `frontend/src/pages/TeamManagement.tsx`
  - Refactored to use the shared creation card and keep its organization refresh/selection behavior.
- `frontend/src/pages/TeamManagement.test.tsx`
- `frontend/src/pages/admin/AdminDashboard.test.tsx` (new)

## 4. Implementation details

### Authorization boundary

- `POST /api/v1/organizations` uses:

  ```python
  Depends(require_permission(Permission.PLATFORM_ORG_MANAGE, strict_auth=True))
  ```

- `super_admin` and the existing legacy `admin` alias are allowed. `organization_admin`, `hr_manager`, `recruiter`, and `candidate` receive `403`.
- A missing or malformed `Authorization` header receives `401`.
- The check is server-side. Frontend visibility is only a usability layer.

### Input validation and normalization

- `name` and `slug` are trimmed in the schema and again in the service.
- Empty or whitespace-only names/slugs are rejected.
- Maximum lengths are enforced: name `255`, slug `100`, description `2000`, domain `255`.
- Slug format is lowercase alphanumerics separated by single hyphens; leading, trailing, and doubled hyphens are rejected.
- Protected fields are rejected with `422` instead of silently ignored.
- Server-controlled defaults:
  - organization status: `active`;
  - creator membership role: `organization_admin`;
  - membership status: `active`;
  - membership join timestamp: server clock.
- No client-supplied role, status, id, creator id, or global role is accepted.

### Transaction and consistency

- Organization and creator membership are created inside `begin_nested()`.
- The request-scoped `get_db` session commits after the endpoint succeeds and rolls back on any exception.
- A duplicate slug returns `409`; the database unique constraint remains the final arbiter under concurrency.
- The creator keeps their existing global role; the new membership never grants platform privileges.

### Audit trail

Successful creation writes an `AuditEventType.ORGANIZATION_CREATED` row with:

- actor user id;
- organization id;
- action `organization_create`;
- resource type/id;
- request correlation id;
- organization name and slug;
- actor role names;
- client IP and user agent;
- success flag.

No password, token, secret, or authorization header is written.

### Frontend

- The creation card is rendered directly on the system **Admin Dashboard** (`/admin/dashboard`), which is protected for `super_admin` and legacy `admin`.
- The same shared card remains available in Team Management for platform admins.
- `organization_admin` cannot see creation controls; if they have no organization, they see a "No Organization Yet" explanation.
- Name input auto-generates a slug until the slug field is edited.
- Client-side validation mirrors the server's name/slug rules.
- Submit button shows loading state and is disabled while a request is in flight.
- A ref guard prevents duplicate submissions before React applies the disabled state.
- On success, the organization list is refreshed from the server, the new organization is selected, and a success banner is shown.
- Server validation and duplicate-slug errors are surfaced through the existing error utility.
- If the post-create refresh fails, the created organization is prepended so a successful creation is not lost.

## 5. Security improvements

- Closed the tenant-creation privilege escalation for candidate, recruiter, HR, and organization-admin accounts.
- Enforced the authorization decision on the server, not in the UI.
- Added strict `401` behavior for anonymous platform-administration requests.
- Rejected mass assignment of protected organization fields.
- Normalized input before validation and persistence.
- Tightened slug validation.
- Made organization + creator membership creation atomic.
- Converted duplicate-slug races into a deterministic `409`.
- Added request-correlated audit logging with actor and tenant context.
- Preserved tenant isolation: creating an organization does not grant any other user access to it.

## 6. Database changes

**None.** No migration was required.

The existing schema already provides:

- a unique index/constraint on `organizations.slug`;
- a unique constraint on `organization_memberships(user_id, organization_id)`;
- server defaults and status/role columns needed by the implementation.

## 7. Tests executed

| Command | Result |
|---|---|
| `python -m pytest tests/test_secure_org_creation.py tests/test_phase2_org.py tests/test_phase1_tenant.py tests/test_phase4_invitation.py -q` | **107 passed** |
| `python -m pytest tests/test_phase4_email.py tests/test_phase5_recruiter_invitation.py tests/test_invitation_link_reachability.py -q` | **65 passed** |
| `python -m pytest tests/test_auth.py tests/test_rbac.py tests/test_rbac_permissions.py tests/test_phase1_security.py tests/test_phase3_registration.py -q` | **213 passed** |
| `npm test -- --run src/pages/TeamManagement.test.tsx src/pages/admin/AdminDashboard.test.tsx` | **11 passed** |
| `npm test -- --run` | **36 files, 441 tests passed** |
| `npx tsc -b` | **Passed** |

The optional full backend suite (`python -m pytest -q`) was started and reached 8% (213 tests) without an observed failure, but was stopped because of its runtime. It is **not** claimed as a completed full-suite run. The targeted suites above are the authoritative regression evidence for this change.

### New backend coverage

`backend/tests/test_secure_org_creation.py` covers:

- super-admin creation and creator membership;
- legacy-admin compatibility;
- `403` for organization admin, HR manager, recruiter, and candidate;
- `401` for anonymous requests;
- trimming of name and slug;
- invalid names and slugs (`422`);
- protected-field rejection (`422`);
- duplicate slug (`409`) without duplicate membership;
- audit actor/org/action/request-id/IP/user-agent content and absence of secrets;
- tenant isolation between platform admins.

### New frontend coverage

`frontend/src/pages/TeamManagement.test.tsx` covers:

- creation controls visible to `super_admin`;
- legacy `admin` compatibility;
- creation controls hidden from `organization_admin`;
- "No Organization Yet" empty state;
- successful create with trimmed input, list refresh, and success banner;
- server conflict message;
- empty-name validation;
- invalid-slug validation;
- duplicate-submit prevention.

`frontend/src/pages/admin/AdminDashboard.test.tsx` covers:

- the shared creation form is rendered directly on the system admin page (`/admin/dashboard`);
- organization name, slug, and submit controls are present after the dashboard loads.

## 8. Manual verification

No interactive browser or live-database walkthrough was performed. Verification was through the ASGI test client and React component tests.

Recommended manual smoke test:

1. Log in as a candidate, recruiter, HR manager, and organization admin; call `POST /api/v1/organizations` and confirm `403`.
2. Call the same endpoint without an `Authorization` header and confirm `401`.
3. Log in as a super admin; create an organization with surrounding whitespace and confirm the stored name/slug are trimmed and the response is `201`.
4. Repeat the same slug and confirm `409`.
5. Submit `id`, `status`, `role`, or `created_by` and confirm `422`.
6. Open the system Admin Dashboard (`/admin/dashboard`) as a super admin and confirm the "Create Organization" card is visible above the metrics.
7. Create an organization and confirm the success banner; then open Team Management and confirm the new organization is selectable and its team list loads.
8. Open Team Management as an organization admin and confirm no creation button is rendered.
9. Query the audit log and confirm the `organization_created` event contains the request id, actor, organization, and no secrets.

## 9. Known limitations

- The full backend suite was not completed; only the relevant and adjacent suites listed above were executed.
- The legacy `admin` role remains a platform-admin alias by design and can still create organizations.
- Failed organization-creation attempts are not audited; only successful creation is required for this phase.
- Organization creation is not rate-limited beyond the existing global middleware.
- The frontend only exposes name and slug even though the API accepts optional description, official email, and domain.
- The frontend check is not a security boundary; the backend dependency is.
- No Phase 2 invitations/acceptance work is included.
- No live browser walkthrough was performed.

## 10. Phase 2 readiness

Phase 1 is ready to serve as the secure tenant-creation foundation for Phase 2.

- Only platform administrators can create tenants.
- Invalid, duplicate, and protected-field inputs are handled predictably.
- The creator receives a scoped `organization_admin` membership, not a global role.
- Tenant isolation and atomicity are covered by tests.
- Existing invitation, email, and recruiter-invitation suites still pass.

Phase 2 can now add invitation creation, delivery, and acceptance on top of this boundary. Phase 2 and Phase 3 behavior were intentionally not implemented here.
