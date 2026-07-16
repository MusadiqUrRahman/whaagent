"""Tests for API authentication."""

import pytest
from fastapi import HTTPException

from whaagent.api.auth import verify_api_key


class TestAPIAuth:
    """Tests for API key authentication."""

    @pytest.mark.asyncio
    async def test_valid_api_key_returns_tenant_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid API key should return tenant_id."""
        from whaagent.config import get_config

        config = get_config(force_reload=True)
        config.auth.api_keys = {"test-key-123": "tenant-1"}

        result = await verify_api_key("test-key-123")
        assert result == "tenant-1"

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid API key should raise 401."""
        from whaagent.config import get_config

        config = get_config(force_reload=True)
        config.auth.api_keys = {"valid-key": "tenant-1"}

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key("invalid-key")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_401(self) -> None:
        """Missing API key should raise 401."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(None)
        assert exc_info.value.status_code == 401
