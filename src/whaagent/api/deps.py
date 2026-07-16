"""FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request

from whaagent.api.auth import verify_api_key
from whaagent.api.security import RateLimiter, validate_tenant_id
from whaagent.storage.database import Database
from whaagent.storage.tenant_manager import TenantManager

TenantId = Annotated[str, Depends(verify_api_key)]

# Module-level rate limiter instance
_rate_limiter = RateLimiter()


async def check_rate_limit(tenant_id: TenantId) -> str:
    """Check rate limit for tenant.

    Args:
        tenant_id: The tenant ID to check for rate limiting.

    Returns:
        The validated tenant ID.

    Raises:
        HTTPException: If rate limit is exceeded.
    """
    validated = validate_tenant_id(tenant_id)
    if not _rate_limiter.is_allowed(validated):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return validated


RateLimitedTenantId = Annotated[str, Depends(check_rate_limit)]


def get_tenant_manager(request: Request) -> TenantManager:
    """Get the tenant manager from app state.

    Args:
        request: The incoming request.

    Returns:
        TenantManager instance.
    """
    return cast(TenantManager, request.app.state.tenant_manager)


def get_database(
    tenant_id: TenantId,
    manager: TenantManager = Depends(get_tenant_manager),
) -> Database:
    """Get database for the current tenant.

    Args:
        tenant_id: The tenant ID from API key verification.
        manager: The tenant manager.

    Returns:
        Database instance for the tenant.
    """
    return manager.get_database(tenant_id)


TenantDB = Annotated[Database, Depends(get_database)]
