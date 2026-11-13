import uuid
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.permissions import Permission, expand_required_roles, user_has_permission
from app.core.security import decode_token
from app.db.session import get_db
from app.domain.models import User
from app.repositories.membership import OrganizationMembershipRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.user import UserService

logger = get_logger(__name__)


async def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


async def get_refresh_token_repo(db: AsyncSession = Depends(get_db)) -> RefreshTokenRepository:
    return RefreshTokenRepository(db)


async def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repo),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repo),
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    return AuthService(user_repo, refresh_token_repo, session=db)


async def get_oauth_service(
    user_repo: UserRepository = Depends(get_user_repo),
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repo),
    db: AsyncSession = Depends(get_db),
):
    from app.services.oauth_service import OAuthService

    return OAuthService(user_repo, refresh_token_repo, session=db)


async def get_user_service(user_repo: UserRepository = Depends(get_user_repo)) -> UserService:
    return UserService(user_repo)


async def _load_user_from_authorization(
    authorization: str,
    user_repo: UserRepository,
) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await user_repo.get_with_roles(uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def get_current_user(
    authorization: str | None = Header(None),
    user_repo: UserRepository = Depends(get_user_repo),
) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await _load_user_from_authorization(authorization, user_repo)


async def get_current_user_strict(
    authorization: str | None = Header(None),
    user_repo: UserRepository = Depends(get_user_repo),
) -> User:
    """Authenticate, reporting a missing header as 401 instead of FastAPI's 422.

    Platform-administration endpoints use this so an anonymous caller is
    unambiguously unauthenticated rather than failed validation.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await _load_user_from_authorization(authorization, user_repo)


def require_role(*roles: str):
    allowed = expand_required_roles(roles)

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = {ur.role.name for ur in current_user.roles}
        if not user_role_names.intersection(allowed):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker


def require_permission(permission: Permission, *, strict_auth: bool = False):
    """Require a global permission.

    ``strict_auth`` makes a missing Authorization header return 401 (used by
    platform-administration endpoints); the default preserves FastAPI's
    existing validation behavior for the rest of the API.
    """
    auth_dependency = get_current_user_strict if strict_auth else get_current_user

    async def permission_checker(
        request: Request,
        current_user: User = Depends(auth_dependency),
    ) -> User:
        user_role_names = [ur.role.name for ur in current_user.roles]
        if not user_has_permission(user_role_names, permission):
            logger.warning(
                "Permission denied: user=%s permission=%s path=%s",
                current_user.id, permission.value, request.url.path,
            )
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission.value}")
        return current_user
    return permission_checker


def require_permissions(*permissions: Permission):
    async def permissions_checker(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role_names = [ur.role.name for ur in current_user.roles]
        missing = [p for p in permissions if not user_has_permission(user_role_names, p)]
        if missing:
            missing_names = [p.value for p in missing]
            logger.warning(
                "Permissions denied: user=%s missing=%s path=%s",
                current_user.id, missing_names, request.url.path,
            )
            raise HTTPException(status_code=403, detail=f"Permissions denied: {', '.join(missing_names)}")
        return current_user
    return permissions_checker


def require_any_role(*roles: str):
    allowed = expand_required_roles(roles)

    async def any_role_checker(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role_names = {ur.role.name for ur in current_user.roles}
        if not user_role_names.intersection(allowed):
            logger.warning(
                "Role access denied: user=%s roles=%s required=%s path=%s",
                current_user.id, list(user_role_names), list(allowed), request.url.path,
            )
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return any_role_checker


def get_current_user_optional(
    authorization: str | None = Header(None),
    user_repo: UserRepository = Depends(get_user_repo),
) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except ValueError:
        return None
    if payload.get("type") != "access":
        return None

    import asyncio

    async def _load() -> User | None:
        user = await user_repo.get_with_roles(uuid.UUID(payload["sub"]))
        if user and user.is_active:
            return user
        return None

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return None
        return loop.run_until_complete(_load())
    except RuntimeError:
        return None


def require_owner_or_role(resource_user_id_fn: Callable, *roles: str):
    allowed = expand_required_roles(roles)

    async def owner_or_role_checker(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role_names = {ur.role.name for ur in current_user.roles}
        if user_role_names.intersection(allowed):
            return current_user

        resource_user_id = await resource_user_id_fn(request)
        if resource_user_id and str(resource_user_id) == str(current_user.id):
            return current_user

        logger.warning(
            "Ownership check failed: user=%s resource_user=%s path=%s",
            current_user.id, resource_user_id, request.url.path,
        )
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return owner_or_role_checker


# ── Organization / Tenant Isolation Dependencies ─────────────────────


async def get_membership_repo(db: AsyncSession = Depends(get_db)) -> OrganizationMembershipRepository:
    return OrganizationMembershipRepository(db)


async def get_current_user_with_org(
    authorization: str | None = Header(None),
    user_repo: UserRepository = Depends(get_user_repo),
    membership_repo: OrganizationMembershipRepository = Depends(get_membership_repo),
    organization_id: uuid.UUID | None = Query(None),
) -> tuple[User, uuid.UUID | None]:
    """Returns current user and optionally verifies organization membership."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user = await user_repo.get_with_roles(uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user, organization_id


class RequireOrgMembership:
    """Dependency that verifies user belongs to the specified organization with an allowed role."""

    def __init__(self, *allowed_roles: str):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
        membership_repo: OrganizationMembershipRepository = Depends(get_membership_repo),
    ) -> User:
        org_id_str = request.path_params.get("organization_id")
        if not org_id_str:
            raise HTTPException(status_code=400, detail="Organization ID required")

        try:
            org_id = uuid.UUID(org_id_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid organization ID")

        membership = await membership_repo.get_active_membership(current_user.id, org_id)
        if not membership:
            logger.warning(
                "Org membership required: user=%s org=%s path=%s",
                current_user.id, org_id, request.url.path,
            )
            raise HTTPException(status_code=403, detail="You are not a member of this organization")

        if self.allowed_roles and membership.role not in self.allowed_roles:
            logger.warning(
                "Org role denied: user=%s org=%s role=%s required=%s path=%s",
                current_user.id, org_id, membership.role, list(self.allowed_roles), request.url.path,
            )
            raise HTTPException(status_code=403, detail="Insufficient organization role")

        request.state.organization_id = org_id
        request.state.membership = membership
        return current_user
