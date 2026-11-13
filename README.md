# AI Hiring Copilot — Phase 4: HR / Admin Invitation Onboarding

Enterprise multi-tenant foundation for an AI-powered hiring and career intelligence platform.

---

## 1. Architecture Overview

### Backend Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Client Layer                         │
│            (React SPA, Mobile, API Clients)              │
└─────────────────────┬────────────────────────────────────┘
                      │ HTTP/JSON
┌─────────────────────▼────────────────────────────────────┐
│                    API Layer (Routers)                    │
│          Thin controllers — no business logic             │
│         /api/v1/auth | /api/v1/users | /api/v1/health    │
└─────────────────────┬────────────────────────────────────┘
                      │ Depends (DI)
┌─────────────────────▼────────────────────────────────────┐
│                  Service Layer                            │
│        All business logic — independent of HTTP           │
│        AuthService | UserService                          │
└─────────────────────┬────────────────────────────────────┘
                      │ Calls
┌─────────────────────▼────────────────────────────────────┐
│                Repository Layer                           │
│     All database operations — no business logic           │
│     UserRepository | BaseRepository<T>                    │
└─────────────────────┬────────────────────────────────────┘
                      │ ORM
┌─────────────────────▼────────────────────────────────────┐
│                Domain Layer                               │
│     SQLAlchemy Models | Pydantic Schemas | Enums          │
│     User | Role | UserRole | RefreshToken                 │
└──────────────────────────────────────────────────────────┘
```

### Frontend Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    App (BrowserRouter)                    │
│   ErrorBoundary → AuthProvider → Routes                   │
└──────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Public      │   │  Protected   │   │  Layout      │
│  Routes      │   │  Routes      │   │  Components  │
│  /login      │   │  /dashboard  │   │  AppLayout   │
│  /register   │   │  /users      │   │  Header      │
└──────────────┘   └──────────────┘   │  Sidebar     │
                                      └──────────────┘
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
        ┌──────────────┐   ┌──────────────────┐
        │  UI Kit      │   │  State Layer     │
        │  Button      │   │  AuthContext      │
        │  Input       │   │  useAuth hook     │
        │  Spinner     │   └──────────────────┘
        └──────────────┘
                           ┌──────────────────┐
                ┌──────────┤  API Layer       │
                ▼          │  client.ts       │
        ┌──────────────┐   │  auth.ts         │
        │  Pages       │   │  interceptors    │
        │  Login       │   └──────────────────┘
        │  Register    │
        │  Dashboard   │
        └──────────────┘
```

### Database Schema

```
┌─────────────────┐       ┌─────────────────┐
│      users      │       │     roles       │
├─────────────────┤       ├─────────────────┤
│ id (UUID)  ──┐  │       │ id (INT)   ──┐  │
│ full_name     │  │       │ name          │  │
│ email         │  │       │ description   │  │
│ password_hash │  │       └──────────┬──────┘
│ is_active     │  │                  │
│ is_verified   │  │       ┌──────────┴──────┐
│ account_status│  │       │   user_roles    │
│ created_at    │  │       ├─────────────────┤
│ updated_at    │  │       │ user_id (FK) ──┼──┐
└──────────┬──────┘  │       │ role_id (FK) ──┼──┘
           │         │       └─────────────────┘
           │         │
┌──────────▼─────────┴──┐    ┌─────────────────────┐
│   refresh_tokens      │    │    organizations     │
├───────────────────────┤    ├─────────────────────┤
│ id (UUID)             │    │ id (UUID)       ──┐ │
│ user_id (FK) ─────────┘    │ name              │ │
│ token_hash                │ slug (UNIQUE)     │ │
│ expires_at                │ description       │ │
│ is_revoked                │ official_email    │ │
│ created_at                │ domain            │ │
│ updated_at                │ logo_url          │ │
└─────────────────────────── │ status            │ │
                              └──────────┬────────┘ │
                                         │          │
                    ┌────────────────────┘          │
                    ▼                               │
        ┌──────────────────────────┐                │
        │  organization_memberships│                │
        ├──────────────────────────┤                │
        │ id (UUID)                │                │
        │ user_id (FK) ────────────┤                │
        │ organization_id (FK) ────┘                │
        │ role                   │
        │ status                 │
        │ invited_by_id (FK)     │
        │ joined_at              │
        │ created_at             │
        └────────────────────────┘
```

**Key relationships:**
- `users` → `user_roles` → `roles`: Legacy flat role assignments (backward compatible)
- `users` → `organization_memberships` → `organizations`: Tenant-scoped roles
- `jobs.organization_id` and `audit_logs.organization_id`: Tenant-owned resources

### Docker Architecture

```
┌──────────────────────────────────────────────────┐
│                  Docker Compose                    │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ postgres │  │  redis   │  │  celery_worker    │ │
│  │ :5432    │  │ :6379    │  │  (background)     │ │
│  └────┬─────┘  └────┬─────┘  └──────────────────┘ │
│       │              │                │             │
│       └──────┬───────┘                │             │
│              ▼                        │             │
│  ┌──────────────────┐                │             │
│  │    backend        │───────────────┘             │
│  │    :8000          │                             │
│  └───────┬──────────┘                             │
│          │ :80                                     │
│  ┌───────▼──────────┐                             │
│  │    frontend       │                             │
│  │    nginx :80      │                             │
│  └──────────────────┘                             │
└──────────────────────────────────────────────────┘
```

---

## 2. API Specification

### Authentication (`/api/v1/auth`)

| Method | Endpoint       | Description          | Auth   |
| ------ | -------------- | -------------------- | ------ |
| POST   | `/register`    | Create new account (candidate only) | No     |
| POST   | `/login`       | Get tokens           | No     |
| POST   | `/refresh`     | Rotate tokens        | No     |
| POST   | `/logout`      | Revoke session       | Yes    |
| GET    | `/me`          | Current user profile + org memberships | Yes    |

### Organizations (`/api/v1/organizations`)

| Method | Endpoint                        | Description                 | Roles                          |
| ------ | ------------------------------- | --------------------------- | ------------------------------ |
| POST   | `/`                             | Create organization         | Any authenticated user         |
| GET    | `/{id}`                         | Get organization            | Org member                     |
| PUT    | `/{id}`                         | Update organization         | organization_admin             |
| GET    | `/me/list`                      | List user's organizations   | Any authenticated user         |
| GET    | `/{id}/members`                 | List org members            | organization_admin, hr_manager |
| PUT    | `/{id}/members/{mid}/status`    | Update member status        | organization_admin             |
| POST   | `/{id}/invitations`             | Create invitation           | organization_admin             |
| GET    | `/{id}/invitations`             | List org invitations        | organization_admin             |
| POST   | `/{id}/invitations/{iid}/revoke`| Revoke invitation           | organization_admin             |
| POST   | `/{id}/invitations/{iid}/resend`| Resend invitation           | organization_admin             |

### Invitations (Public)

| Method | Endpoint              | Description              | Auth |
| ------ | --------------------- | ------------------------ | ---- |
| GET    | `/invitations/validate/{token}` | Validate invitation token; returns org name, role, invited email, expiry and `existing_user` flag | No   |
| POST   | `/invitations/accept`  | New-user acceptance: creates account bound to the invited email | No   |
| POST   | `/invitations/accept-signed-in` | Existing-user acceptance: requires Bearer auth; backend enforces `authenticated_user.email == invitation.email` | Yes  |

Invitation email CTA: `{FRONTEND_BASE_URL}/invite/{token}` (frontend route
`/invite/:token`; `/invite/accept/:token` kept as legacy alias).

**Invitable roles (Phase 5):** `recruiter`, `hr_manager`, `organization_admin`.
Only organization admins may invite. `candidate` is public self-registration;
platform roles are never invitable. See ADR-003 Amendment 2.

### Users (`/api/v1/users`)

| Method | Endpoint              | Description       | Roles     |
| ------ | --------------------- | ----------------- | --------- |
| GET    | `/`                   | List all users    | admin     |
| GET    | `/{id}`               | Get user by ID    | admin, hr |
| PATCH  | `/{id}`               | Update user       | admin     |
| DELETE | `/{id}`               | Delete user       | admin     |
| POST   | `/{id}/roles/{name}`  | Assign role       | admin     |
| DELETE | `/{id}/roles/{name}`  | Remove role       | admin     |

### Health (`/api/v1/health`)

| Method | Endpoint      | Description               |
| ------ | ------------- | ------------------------- |
| GET    | `/health`     | System health check       |
| GET    | `/health/ready` | Readiness probe        |

Swagger docs: `/docs`  
OpenAPI schema: `/openapi.json`

---

## 3. Folder Structure

```
hire/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── health.py
│   │   │   │   ├── users.py
│   │   │   │   ├── organizations.py
│   │   │   │   └── invitations.py
│   │   │   ├── __init__.py
│   │   │   ├── deps.py          # DI wiring
│   │   │   └── errors.py        # Exception handlers
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic settings
│   │   │   ├── exceptions.py    # App exception classes
│   │   │   ├── logging.py       # Logger config
│   │   │   ├── middleware.py    # Logging + rate limiting
│   │   │   ├── security.py      # JWT + bcrypt
│   │   │   ├── security_middleware.py  # Security headers + audit
│   │   │   └── permissions.py   # RBAC + enterprise permissions
│   │   ├── db/
│   │   │   ├── base.py          # DeclarativeBase + mixins
│   │   │   ├── session.py       # Async engine + session
│   │   │   └── __init__.py
│   │   ├── domain/
│   │   │   ├── enums.py         # RoleName, AccountStatus, etc.
│   │   │   ├── models.py        # SQLAlchemy models
│   │   │   ├── schemas.py       # Pydantic schemas
│   │   │   ├── schemas_organization.py  # Org/membership schemas
│   │   │   └── __init__.py
│   │   ├── repositories/
│   │   │   ├── base.py          # BaseRepository[T]
│   │   │   ├── user.py          # UserRepository
│   │   │   ├── organization.py  # OrganizationRepository
│   │   │   ├── membership.py    # OrganizationMembershipRepository
│   │   │   ├── invitation.py    # InvitationRepository
│   │   │   └── audit_log.py     # AuditLogRepository
│   │   ├── services/
│   │   │   ├── auth.py          # AuthService
│   │   │   ├── user.py          # UserService
│   │   │   ├── organization_service.py  # Org + membership
│   │   │   ├── invitation_service.py    # Invitation lifecycle
│   │   │   └── audit_service.py         # Security audit
│   │   ├── workers/
│   │   │   ├── celery_app.py    # Celery config
│   │   │   ├── tasks.py         # Task definitions
│   │   │   └── __init__.py
│   │   └── main.py              # FastAPI app + startup seeding
│   ├── alembic/
│   │   ├── versions/
│   │   │   ├── 0001_initial_schema.py
│   │   │   └── 0012_enterprise_identity_org.py
│   │   ├── env.py
│   │   └── alembic.ini
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_rbac.py
│   │   ├── test_phase1_security.py
│   │   ├── test_phase1_tenant.py
│   │   ├── test_phase2_org.py
│   │   ├── test_phase3_registration.py
│   │   ├── test_phase4_invitation.py
│   │   ├── test_db.py
│   │   └── test_health.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── api/
│   │   │   ├── auth.ts          # Auth + org API calls
│   │   │   ├── client.ts        # Axios instance + interceptors
│   │   │   └── interceptors.ts
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   └── LoadingSpinner.tsx
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.tsx
│   │   │   │   ├── Header.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── ErrorBoundary.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx
│   │   ├── hooks/
│   │   │   ├── useApi.ts
│   │   │   └── useAuth.ts
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Register.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── TeamManagement.tsx
│   │   │   └── InviteAccept.tsx
│   │   ├── types/
│   │   │   ├── api.ts
│   │   │   └── auth.ts
│   │   ├── utils/
│   │   │   ├── storage.ts       # Token storage
│   │   │   └── validation.ts    # Form validators
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── nginx.conf
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── Dockerfile
│   └── .env.example
├── docs/
│   └── adr/
│       ├── 001-multi-tenant-organization-model.md
│       ├── 002-candidate-only-public-registration.md
│       └── 003-controlled-hr-admin-invitation-onboarding.md
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 4. Development Setup

### Prerequisites

- Docker & Docker Compose
- Python 3.14 (for local development)
- Node.js 22+ (for local frontend development)

### Quick Start (Docker)

```bash
# 1. Clone and enter the project
cd hire

# 2. Copy environment file
cp .env.example .env

# 3. Start all services
docker compose up --build

# 4. Verify health
curl http://localhost:8000/api/v1/health
```

Services will be available at:

| Service  | URL                        |
| -------- | -------------------------- |
| Frontend | http://localhost           |
| Backend  | http://localhost:8000      |
| Swagger  | http://localhost:8000/docs |
| Postgres | localhost:5432             |
| Redis    | localhost:6379             |

### Local Development (Backend)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env to point to local postgres
alembic upgrade head
uvicorn app.main:app --reload
```

### Local Development (Frontend)

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest -v --asyncio-mode=auto
```

---

## 5. Security Checklist

- [x] Passwords hashed with bcrypt (via passlib)
- [x] JWT access tokens (short-lived, 30 min)
- [x] JWT refresh tokens (long-lived, 7 days, rotatable)
- [x] OAuth2 password flow
- [x] CORS whitelist configured
- [x] Rate limiting on API endpoints
- [x] Input validation (Pydantic + regex)
- [x] SQL injection protection (via SQLAlchemy ORM)
- [x] Registration restricted to candidate role only
- [x] Privilege escalation prevention (privileged roles require invitation)
- [x] Account status system (active/inactive/suspended/deactivated)
- [x] Multi-tenant organization isolation
- [x] Invitation-based onboarding with token expiry
- [x] Audit logging for security events
- [x] Email normalization (case-insensitive, whitespace-trimmed)
- [x] Mass assignment protection (role, org_id, permissions ignored)
- [x] Password never returned in API responses
- [x] Invitation role restriction (hr_manager + organization_admin only)
- [x] Invitation token security (SHA-256 hash, high entropy, single-use)
- [x] Invitation resend capability (expired/pending)
- [x] Duplicate membership prevention (409 Conflict)
- [x] Cross-organization invitation protection
- [ ] MFA support (architecture prepared — add TOTP verification in AuthService)
- [ ] HTTPS in production (terminate at reverse proxy)
- [ ] httpOnly cookies for refresh tokens (enhancement option)

---

## 6. Scalability Considerations

- **Async-first**: SQLAlchemy async sessions, non-blocking I/O
- **Connection pooling**: 20 pool size, 10 overflow — configurable
- **Stateless backend**: Horizontally scalable (no server-local state)
- **Redis caching layer**: Prepared for caching decisions/scores/fairness results
- **Celery workers**: Background task processing, can scale independently
- **Database indexing**: UUID primary keys, email index, user_id index on FK tables
- **Read replicas**: Architecture supports read/write splitting via session factory config
- **API versioning**: `/api/v1/` prefix ensures backward compatibility

---

## 7. Production Readiness Checklist

- [ ] Set strong `SECRET_KEY` in production
- [ ] Enable HTTPS with valid TLS certificate
- [ ] Configure production-grade PostgreSQL (HA, backups)
- [ ] Use managed Redis (ElastiCache, Upstash)
- [ ] Set up CI/CD pipeline (GitHub Actions, GitLab CI)
- [ ] Configure monitoring (Prometheus + Grafana)
- [ ] Set up centralized logging (ELK, Datadog)
- [ ] Configure container orchestration (Kubernetes / ECS)
- [ ] Run Alembic migrations as part of deployment
- [ ] Set up database backup strategy
- [ ] Configure CDN for static assets
- [ ] Set up alerting for health endpoint failures
- [ ] Run security audit (dependency scanning, SAST)
- [ ] Load test all API endpoints
- [ ] Set up staging environment mirroring production

---

## 8. Design Decisions

| Decision                | Rationale                                              |
| ----------------------- | ------------------------------------------------------ |
| Async SQLAlchemy        | Non-blocking DB access for concurrent requests         |
| Repository pattern      | Swap DB providers without touching services            |
| Service layer           | Business logic testable without HTTP                   |
| Thin routers            | Easy to version, swap, or migrate API surface          |
| UUID primary keys       | Safe for distributed systems, no sequential guessing   |
| Refresh token rotation  | Old refresh tokens invalidated on each refresh         |
| Axios interceptors      | Centralized token injection + refresh queue            |
| Context API (no Redux)  | Sufficient for auth state in Phase 0                   |
| Slug-based org IDs      | Stable, human-readable org identifiers for URLs        |
| Candidate-only register | Prevents privilege escalation via public registration   |
| Invitation-based onboarding | Privileged roles require org admin approval        |
| Tenant ownership on jobs | Jobs scoped to organizations for data isolation     |
| Email normalization | Case-insensitive, whitespace-trimmed at schema + service layer |
| Explicit registration DTO | RegisterRequest has no role field — mass assignment safe |
| See `docs/adr/001-multi-tenant-organization-model.md` | Full ADR for multi-tenant architecture |
| See `docs/adr/002-candidate-only-public-registration.md` | Full ADR for registration security |
| See `docs/adr/003-controlled-hr-admin-invitation-onboarding.md` | Full ADR for invitation security |

---

## 9. Future Phase Integration Points

Phase 4 establishes controlled HR/admin invitation onboarding. Future phases build on this:

| Future Module           | Integration Point                                    |
| ----------------------- | ---------------------------------------------------- |
| Candidate Management    | Tenant-scoped candidate pools via job relationships  |
| Resume Parsing          | Celery task + repository for parsed document data    |
| Candidate Ranking       | New service + API router under `/api/v1/ranking`     |
| Fairness Analysis       | Audit service consuming candidate data               |
| Interview Scheduling    | Celery task for notifications + calendar integration |
| AI Copilot Chat         | WebSocket endpoint + AI service layer                |
| MFA                     | `verify_mfa()` step in `AuthService.login()`         |
| Role-based Dashboards   | New protected routes with role checks                |
| Tenant Admin Panel      | Super admin management of all organizations          |
| Cross-org Analytics     | Platform-wide analytics with tenant filtering        |

---

## 10. Phase 11 — AI Demo Data Generator & Recruitment Simulation

One-click synthetic recruitment ecosystem for demos and evaluation (admin-only,
`/admin/demo` in the UI; APIs under `/api/v1/demo`, guarded by admin RBAC).

- **Scenarios (13 presets)**: Quick Start, Full Pipeline, Screening Only, Talent
  Pool, plus named industry drives — Campus Placement, Startup Hiring,
  Enterprise Hiring, IT Company, Healthcare, Mass Hiring, Remote Hiring,
  Finance Recruitment, Government Recruitment (`app/services/demo/data_pool.py`
  holds the industry company/title/skill pools).
- **Customization knobs**: companies count, jobs, candidates, recruiters,
  candidates-per-job, hiring difficulty (`easy|medium|hard`), skill categories,
  resume format (PDF/DOCX/TXT), RNG seed.
- **Pipeline simulation**: companies → staff → candidates (profiles + real
  PDF/DOCX resumes parsed by the existing parser) → published jobs →
  applications → AI screening & ranking → interviews with scorecards →
  **hiring decisions** (shortlist → offer → hired/rejected, difficulty-aware)
  → analytics reports → agent knowledge indexing.
- **Timeline**: every stage emits `SimulationEvent`s plus audit logs
  (`demo.generate`, `demo.decisions`); progress is pollable via
  `GET /demo/status` / `GET /demo/runs/{id}`.
- **Safety**: reset deletes only demo-domain data
  (`@hirecraft.demo`) tracked per run — real users/organizations are untouched.
  Export returns the full dataset as JSON.

Tests: `tests/test_demo_platform.py`, `tests/test_phase11_demo_extensions.py`.

---

## 11. Deliverables Summary

### Phase 0 (Complete)
- [x] Complete folder structure
- [x] Backend architecture diagram (above)
- [x] Frontend architecture diagram (above)
- [x] Database schema diagram (above)
- [x] Docker architecture diagram (above)
- [x] API specification (above)
- [x] Development setup instructions
- [x] Security checklist
- [x] Scalability considerations
- [x] Production readiness checklist

### Phase 1: Identity + Authorization (Complete)
- [x] Registration restricted to candidate role
- [x] Privilege escalation prevention
- [x] Account status system (active/inactive/suspended/deactivated)
- [x] Audit logging for security events
- [x] Enterprise RBAC with 60+ permissions
- [x] Legacy role mapping for backward compatibility

### Phase 2: Organization / Tenant Foundation (Complete)
- [x] Organization model (UUID PK, slug, status)
- [x] Organization membership with scoped roles
- [x] Invitation-based onboarding (token, expiry, lifecycle)
- [x] Tenant isolation (RequireOrgMembership dependency)
- [x] Slug validation (lowercase alphanumeric + hyphens)
- [x] N+1 query optimization for org listing
- [x] Demo organizations seeded on startup
- [x] Frontend: TeamManagement, InviteAccept pages
- [x] Alembic migration 0012 (SQLite-compatible)
- [x] 146 tests passing (auth + RBAC + security + tenant + org)
- [x] ADR for multi-tenant architecture
- [x] README updated

### Phase 3: Candidate Self-Registration (Complete)
- [x] Email normalization (case-insensitive, whitespace-trimmed)
- [x] Mass assignment protection (role, org_id, permissions, is_superuser ignored)
- [x] Candidate-only enforcement (backend + frontend)
- [x] Password never leaked in API responses
- [x] Account status for new registrations (active, not verified)
- [x] Password strength validation (8+ chars, uppercase, lowercase, digit)
- [x] Backward compatibility with existing auth flows
- [x] 37+ new tests (email normalization, mass assignment, security)
- [x] ADR for candidate-only registration
- [x] README updated

### Phase 4: HR / Admin Invitation Onboarding (Complete)
- [x] Invitation role restriction (hr_manager + organization_admin only)
- [x] Recruiter role removed from valid invitation roles
- [x] Email normalization on invitations (case-insensitive, whitespace-trimmed)
- [x] Invitation token security (SHA-256 hash, high entropy, single-use)
- [x] Raw token never stored, logged, or returned by list/validate APIs
- [x] Invitation lifecycle (pending → accepted/expired/revoked)
- [x] Configurable expiry via `INVITATION_EXPIRATION_HOURS` (default 72)
- [x] Acceptance flow for new users (register + join org)
- [x] Acceptance flow for existing users (signed-in; server-side email-match enforcement)
- [x] Atomic single-use consumption (race-safe conditional UPDATE)
- [x] Email notification queued AFTER DB commit via existing Celery worker
- [x] Professional HTML invitation email (Jinja2 autoescape, frontend CTA link)
- [x] `email_status` in API responses (queued/sent/skipped/error) — distinct from invitation status
- [x] Resend capability with token rotation (old token invalidated)
- [x] Revoke capability (invitation URL immediately invalid)
- [x] Duplicate membership prevention (409 Conflict)
- [x] Cross-organization invitation protection
- [x] Frontend: `/invite/:token` acceptance page (loading/valid/expired/revoked/accepted/mismatch states)
- [x] Frontend: existing-user flow ("Sign In to Accept" → returns via same-app redirect)
- [x] Frontend: TeamManagement invite form + pending-invitation table (Resend/Revoke)
- [x] Backward compatibility with existing auth flows
- [x] 62 Phase 4 tests (authorization, role escalation, token security, lifecycle, email, Celery)
- [x] ADR-003 amended for email flow + signed-in acceptance
- [x] README updated

### HR/Admin Onboarding Flow

```
Organization Admin
        ↓  POST /organizations/{id}/invitations (email, hr_manager|organization_admin)
Invitation persisted (token hash only)  →  COMMIT  →  Celery task queued
        ↓
Invitee receives "You've been invited to join {Org}" email
        ↓  [ Accept Invitation ]  →  {FRONTEND_BASE_URL}/invite/{token}
Frontend validates token (GET /invitations/validate/{token})
        ↓
New user: account created from invited email only
Existing user: signs in; backend enforces email match
        ↓
Organization membership created; invitation marked accepted (single-use)
        ↓
HR / Admin access
```

Registration policy summary:

| Role              | Onboarding                          |
| ----------------- | ----------------------------------- |
| Candidate         | Public self-registration            |
| HR Manager        | Invitation only (this phase)        |
| Organization Admin| Invitation only (this phase)        |
| Recruiter         | Phase 5 (not invitable yet)         |
| Platform Admin    | Out of scope (never publicly invitable) |

---

## 12. Phase 12 - AI Technical & Aptitude Assessment Platform

Upgrades Interview Intelligence into a full assessment platform: recruiters compose
assessments from 17 AI-generated question types; candidates take them under a live
timer with integrity logging; every answer is auto-graded by rule-based engines
(no external LLM dependency), producing section/skill analytics and hiring recommendations.

### Question Types (17)

| Category | Types |
| --- | --- |
| Objective | Technical MCQ, SQL theory MCQ, CS fundamentals, code-output prediction, aptitude (quantitative / logical / verbal) |
| Code | Coding challenges (sandboxed execution vs hidden test cases), debugging, code output |
| SQL | Query writing graded by executing on an isolated in-memory SQLite database (partial credit) |
| Subjective | System design (rubric-keyword grading), scenario, case study, behavioral (resume-aware), situational judgment |

### Engines (`backend/app/services/assessment/`)

- **question_banks.py** - curated + parametric banks: technical MCQs per skill,
  11 quantitative generators, logical series/coding-decoding generators, coding
  problems (easy/medium/hard) with verified reference solutions, SQL schema +
  reference queries (incl. window functions), system-design prompts with rubrics.
- **generators.py** - `generate_assessment_questions(sections, seed)` builds
  deterministic papers from section configs (type/count/difficulty/skills).
- **validator.py** - structural QC + fingerprint dedupe; invalid questions are dropped.
- **code_sandbox.py** - `CodeSandbox` runs untrusted Python in Docker
  (no network, memory/CPU/PID limits) or a restricted local subprocess fallback;
  harness-based test-case execution with wall-clock timeout. `SqlGrader` executes
  candidate SQL on an isolated seeded SQLite DB and forbids mutating statements.
  `estimate_complexity` gives a static heuristic complexity label.
- **graders.py** - objective exact match (+partial for code output), rubric-keyword
  subjective grading, debugging keyword+fix detection, coding score = passed/total tests.
- **adaptive.py** - easy -> medium -> hard -> expert ladder (2-correct streak up, wrong down).
- **scoring.py** - section/skill/difficulty scores, negative marking (objective only),
  accuracy & time management, readiness level, recommendation
  (`strong_hire >=85`, `hire >=70`, `consider >=passing`, else `reject`).

### API (`/api/v1/assessments`)

Recruiter: `POST /generate`, `GET ""`, `GET /{id}`, `GET /{id}/analytics`.
Candidate: `GET /me`, `POST /{id}/start`, `GET /attempts/{id}` (sanitized state),
`POST /{attempt_id}/answer`, `POST .../code/run`, `POST .../code/submit`,
`POST .../integrity`, `POST .../submit` (finalize+score), `GET /{attempt_id}/result`
(owner or staff visibility).

### Frontend pages (`frontend/src/pages/assessments/`)

- Recruiter: **AssessmentLibrary** (`/recruiter/assessments`),
  **AssessmentBuilder** (`/recruiter/assessments/builder`),
  **RecruiterAnalytics** (`/recruiter/assessments/:id/analytics`).
- Candidate: **MyAssessments** (`/candidate/assessments`),
  **TakeAssessment** (`/candidate/assessments/take/:assessmentId`; timer, integrity
  events, instant objective feedback, run-tests-before-submit for coding),
  **AssessmentResult** (`/candidate/assessments/results/:attemptId`).

### Data model

7 new tables via `create_all`: `assessments`, `assessment_questions`, `test_cases`,
`candidate_assessments` (per-attempt question order, integrity events),
`candidate_answers`, `coding_submissions`, `assessment_results`.

### Testing

30 dedicated tests in `backend/tests/test_phase12_assessment_platform.py`
(generation determinism, bank validity across seeds, validator rejections, all
graders, sandbox incl. timeout/error paths, SqlGrader incl. forbidden statements,
scoring thresholds & negative marking, adaptive ladder, full API lifecycle,
timer expiry, attempt limits, RBAC matrix, result visibility, regression sanity).
Full suite: **761 passed** (731 pre-existing + 30 new).

### Limitations

- Rule-based grading only: subjective answers are scored on rubric coverage /
  structure evidence, not semantic understanding.
- Complexity labels are static heuristics, not measured profiles.
- Sandbox uses local subprocess fallback unless Docker is configured
  (`settings.assessment_sandbox = "docker"`).
- Candidate discovers assessments via shared take-links (no candidate-facing catalog).

---

## 13. Phase 14 - Simulation Intelligence / Hiring Strategy Sandbox

Recruiters and HR staff build "what-if" hiring-strategy scenarios on top of a real job:
pick a target job, snapshot its current screening setup as the **baseline**, then edit a
hypothetical **simulation configuration** (scoring weights, pass threshold, shortlist
size, mandatory/preferred skills, experience/education requirements) to experiment before
committing to changes.

### Data model

New table `simulation_scenarios` (Alembic migration `0016_simulation_intelligence`):

- Identity: `id` (UUID), `organization_id`, `job_id`, `created_by`.
- Naming: `name`, `description`.
- Snapshot: `baseline_config` (JSON) — frozen snapshot of the job's screening setup
  (source `job_snapshot`, job id/version/title/company, default weights, threshold 70,
  shortlist size 10, requirements seed with the job's skills).
- Proposed: `simulation_config` (JSON) — the editable what-if configuration; when
  omitted at creation it defaults to a copy of the baseline configuration.
- Lifecycle: `status`, `config_version` (bumped on every config edit), `metadata`.
- Timestamps: `created_at`, `updated_at`, `completed_at`.
- Indexes: `organization_id`, `job_id`, `created_by`, `status`.

### Status lifecycle

`draft` → `ready` (mark ready); `ready` → `queued` → `running` → `completed`
(via the execution engine); any run may `failed`; `queued`/`running` runs can be
`cancelled`; `ready` ↔ `draft`; `draft` → `cancelled`; `cancelled` → `draft`.
Scenarios in `ready`, `completed`, and `failed` can be re-run. Only `draft` and
`cancelled` scenarios are editable; editing bumps the config version and writes an
audit event.

### Execution engine (`simulation_executions`, migration `0017`)

Running a scenario snapshots its current configuration, deterministically scores the
live candidate pool through the **same `MatchingEngine`** (`threshold` + weighted
dimensions) under both the baseline and the simulation configs, and persists only
simulation-scoped rows — live `jobs`/`applications`/`candidate_rankings` are never
modified (an acceptance test asserts live rows are byte-for-byte unchanged). Failed /
cancelled runs keep a partial result set so the UI can still show what was scored.

### API (`/api/v1/simulations`, roles `admin`/`hr`/`recruiter`)

- `GET /simulations` — list own + org-scoped scenarios with stats by status.
- `POST /simulations` — create a scenario from a job (baseline snapshot + config).
- `GET /simulations/{id}` — full scenario detail (metadata, configs).
- `GET /simulations/{id}/status` — status + `can_edit` flag.
- `PATCH /simulations/{id}` — edit name/description/config or transition status.
- `DELETE /simulations/{id}` — delete (audited).
- `POST /simulations/{id}/run` — start an execution (422 on invalid config with
  `extra.validation_errors`; 409 on a duplicate active run).
- `GET /simulations/{id}/executions` — execution history for the scenario.
- `GET /simulations/{id}/executions/{execution_id}` — single execution detail.
- `POST /simulations/{id}/executions/{execution_id}/cancel` — cancel a queued/running run.
- `GET /simulations/{id}/results` — paginated/sortable candidate-level results with
  `change_filter` (improved/declined/entered/left shortlist/qualified/disqualified).
- `GET /simulations/{id}/summary` — aggregate summary, impact metrics, major movers
  (optionally scoped to an `execution_id`).

Tenant isolation mirrors the jobs model: org members and the creator can view;
org admins / HR managers / HR plus the creator can modify; platform admins bypass;
non-members get 403; missing scenarios/jobs return 404.

### Frontend pages (`/recruiter/simulations*`)

- **SimulationDashboard** (`/recruiter/simulations`) — stat cards by status, job
  table with View/Delete, empty states (no jobs → prompt to post one; no scenarios
  → prompt to create one).
- **CreateSimulation** (`/recruiter/simulations/create`) — job selector, name and
  description, side-by-side baseline-vs-simulation builder seeded from the selected
  job's screening setup.
- **SimulationDetails** (`/recruiter/simulations/:simulationId`) — status badge,
  config version/timestamps, read-only baseline and simulation summaries, edit
  mode (draft/cancelled only), Mark Ready / Return to Draft / Delete actions, a
  **Run Simulation** button (ready/completed/failed) with live polling while a run
  is in flight, cancellation, a run-history panel, and a latest-run summary.
- **SimulationResults** (`/recruiter/simulations/:simulationId/results`) — execution
  selector (defaults to the latest completed run, 2s polling while active), summary
  cards (threshold, shortlist, avg score), impact metrics, pool movement, major
  movers, and a paginated, sortable candidate table with per-candidate
  baseline-vs-simulation ranks/scores, qualification and shortlist chips, and
  change reasons.

### Backend implementation

- `Domain`: `app/domain/simulation_models.py`, `app/domain/simulation_schemas.py`
  (validation: weights bounded to [0,1] with a non-zero dimension, threshold 0-100,
  shortlist size 1-500, `metadata` serialization alias; execution/result schemas
  with from-attributes serialization).
- `Repository`: `app/repositories/simulation.py` (`get_with_details`, `get_by_job`,
  `list_by_creator`, `list_by_org`, `list_visible`, `count_by_status`);
  `app/repositories/simulation_execution.py` (executions + result rows).
- `Service`: `app/services/simulation/simulation_service.py` (permission helpers,
  baseline snapshots, config-version increment, audit events on create/update/delete);
  `app/services/simulation/evaluation.py` (baseline + simulation scoring, rank
  mapping, shortlist/qualification, change reasons, impact metrics);
  `app/services/simulation/execution_service.py` (lifecycle, persistence of
  simulation-scoped rows, cancel).
- `Router`: `app/api/v1/simulations.py` registered at `app.main` under `/api/v1`.
- `Migrations`: `backend/alembic/versions/0016_simulation_intelligence.py`,
  `backend/alembic/versions/0017_simulation_execution.py`.

### Testing

Dedicated tests in `backend/tests/test_simulations.py` (26) and
`test_simulation_validation.py` (32), plus `test_simulation_phase3.py` (20:
lifecycle, aggregate/result schemas, baseline-vs-sim scoring parity, rank mapping,
persistence, invalid config at run time 422, duplicate active run 409, cancellation,
re-run, and the live-row immutability acceptance test). Full suite: **988 passed**.
Frontend: 55 tests (`types/simulations.test.ts`, `ScenarioStatusBadge.test.tsx`,
routing/smoke suites) plus the production build (`tsc -b && vite build`).

### Limitations

- One candidate pool per scenario step: each run scores the live pool under the
  scenario's config snapshot; multi-scenario cohort comparison and cross-scenario
  analytics are deferred.
- Deterministic rule-based scoring only: explainability, fairness
  metrics, adversarial analysis, and the skill-graph timeline are future phases.


