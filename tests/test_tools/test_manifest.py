"""Tests for tool manifest client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestToolManifestClient:
    """Tests for ToolManifestClient."""

    @pytest.mark.asyncio
    async def test_fetch_manifest_from_toolbox(self) -> None:
        """Client should fetch manifest from toolbox server."""
        from whaagent.tools.manifest import ToolManifestClient

        mock_response = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "version": "1.0.0",
                "tools": [{"name": "web_search", "category": "web", "description": "Search"}],
            }
        )

        with patch("whaagent.tools.manifest.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.get = AsyncMock(return_value=mock_response)
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_context

            client = ToolManifestClient("http://localhost:8080")
            manifest = await client.fetch_manifest()

        assert manifest is not None
        assert len(manifest.tools) == 1
        assert manifest.tools[0].name == "web_search"

    @pytest.mark.asyncio
    async def test_get_cached_manifest(self) -> None:
        """Client should cache manifest."""
        from whaagent.tools.manifest import ToolManifestClient

        client = ToolManifestClient("http://localhost:8080")

        # Mock the first fetch
        with patch.object(client, "fetch_manifest", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MagicMock(tools=[])
            await client.get_manifest()
            assert mock_fetch.call_count == 1

            # Second call should use cache
            await client.get_manifest()
            assert mock_fetch.call_count == 1  # Not called again
