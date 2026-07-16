"""Tests for MCP tool response interceptors."""

import pytest
from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from mcp.types import CallToolResult, ImageContent, TextContent

from whaagent.mcp.interceptors import DEFAULT_MAX_RESPONSE_SIZE, ResponseTruncator


def _make_request() -> MCPToolCallRequest:
    """Create a minimal MCPToolCallRequest for testing."""
    return MCPToolCallRequest(
        name="test_tool",
        args={},
        server_name="test_server",
    )


async def _invoke(
    truncator: ResponseTruncator,
    result: CallToolResult | ToolMessage,
) -> CallToolResult | ToolMessage:
    """Helper to run a truncator with a handler that returns the given result."""

    async def handler(
        request: MCPToolCallRequest,
    ) -> CallToolResult | ToolMessage:
        return result

    return await truncator(request=_make_request(), handler=handler)


class TestResponseTruncator:
    """Tests for ResponseTruncator interceptor with truncation enabled."""

    @pytest.mark.asyncio
    async def test_passes_through_small_responses(self) -> None:
        """Small responses should pass through unchanged."""
        truncator = ResponseTruncator(max_response_size=1000)

        original_result = CallToolResult(
            content=[TextContent(type="text", text="hello world")],
        )

        result = await _invoke(truncator, original_result)
        assert result == original_result

    @pytest.mark.asyncio
    async def test_truncates_large_text_responses(self) -> None:
        """Large text responses should be truncated near the limit."""
        truncator = ResponseTruncator(max_response_size=100)

        original_result = CallToolResult(
            content=[TextContent(type="text", text="x" * 500)],
        )

        result = await _invoke(truncator, original_result)
        assert isinstance(result, CallToolResult)
        text = result.content[0].text  # type: ignore[union-attr]
        assert len(text) < 200  # truncated + notice
        assert "truncated" in text.lower()
        assert "500" in text  # shows original size

    @pytest.mark.asyncio
    async def test_truncates_at_paragraph_boundary(self) -> None:
        """Truncation should prefer paragraph breaks when possible."""
        truncator = ResponseTruncator(max_response_size=100)

        # Create text with paragraph break in the first half
        body = "a" * 40 + "\n\n" + "b" * 200
        original_result = CallToolResult(
            content=[TextContent(type="text", text=body)],
        )

        result = await _invoke(truncator, original_result)
        assert isinstance(result, CallToolResult)
        text = result.content[0].text  # type: ignore[union-attr]
        # Should cut at the paragraph break, not mid-word
        assert "a" * 40 in text
        assert "truncated" in text.lower()

    @pytest.mark.asyncio
    async def test_preserves_non_text_content(self) -> None:
        """Non-text content blocks should be passed through."""
        truncator = ResponseTruncator(max_response_size=100)

        image_block = ImageContent(type="image", data="abc", mimeType="image/png")
        original_result = CallToolResult(
            content=[
                TextContent(type="text", text="x" * 500),
                image_block,
            ],
        )

        result = await _invoke(truncator, original_result)
        assert isinstance(result, CallToolResult)
        types = [c.type for c in result.content]  # type: ignore[union-attr]
        assert "image" in types

    @pytest.mark.asyncio
    async def test_preserves_is_error_flag(self) -> None:
        """isError flag should be preserved through truncation."""
        truncator = ResponseTruncator(max_response_size=100)

        original_result = CallToolResult(
            content=[TextContent(type="text", text="x" * 500)],
            isError=True,
        )

        result = await _invoke(truncator, original_result)
        assert isinstance(result, CallToolResult)
        assert result.isError is True

    @pytest.mark.asyncio
    async def test_default_max_size_is_5k(self) -> None:
        """Default max_response_size should be 5000."""
        truncator = ResponseTruncator()
        assert truncator.max_response_size == DEFAULT_MAX_RESPONSE_SIZE
        assert truncator.max_response_size == 5_000

    @pytest.mark.asyncio
    async def test_tool_message_passes_through(self) -> None:
        """ToolMessage results should pass through unchanged."""
        truncator = ResponseTruncator(max_response_size=100)

        tool_msg = ToolMessage(
            content="x" * 500,
            tool_call_id="test-call-id",
        )

        result = await _invoke(truncator, tool_msg)
        assert result == tool_msg

    @pytest.mark.asyncio
    async def test_empty_content_passes_through(self) -> None:
        """Empty content list should pass through unchanged."""
        truncator = ResponseTruncator(max_response_size=100)

        original_result = CallToolResult(content=[])

        result = await _invoke(truncator, original_result)
        assert isinstance(result, CallToolResult)
        assert result.content == []
