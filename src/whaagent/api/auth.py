"""API authentication utilities."""

from typing import Optional

from fastapi import Header, HTTPException

from whaagent.config import get_config


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Verify API key and return tenant_id.

    Args:
        x_api_key: API key from X-API-Key header.

    Returns:
        tenant_id associated with the API key.

    Raises:
        HTTPException: If API key is missing or invalid.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include X-API-Key header.",
        )

    config = get_config()
    tenant_id = config.auth.api_keys.get(x_api_key)

    if tenant_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
        )

    return tenant_id
