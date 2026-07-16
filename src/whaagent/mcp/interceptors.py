"""MCP tool call interceptors for response processing."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Union

from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from mcp.types import CallToolResult, TextContent

logger = logging.getLogger(__name__)

# Default maximum response size in characters (~5K tokens).
# Enough for useful content without bloating the LLM context window.
DEFAULT_MAX_RESPONSE_SIZE = 5_000

# The result type from the handler chain.  We only intercept
# ``CallToolResult`` (the raw MCP response).  ``ToolMessage`` and
# ``Command`` are LangGraph-level wrappers that are already shaped by
# higher-level interceptors, so we pass them through untouched.
try:
    from langgraph.types import Command  # noqa: F401

    _HandlerResult = Union[CallToolResult, ToolMessage, Command]  # type: ignore[misc]
except ImportError:
    _HandlerResult = Union[CallToolResult, ToolMessage]  # type: ignore[misc]


class ResponseTruncator:
    """ToolCallInterceptor that truncates oversized MCP tool responses.

    This is a defense-in-depth layer: even if an MCP server returns large
    responses, this interceptor truncates them before they enter the LLM
    context window. This prevents the 100s-of-KB responses that cause
    model confusion and excessive latency.

    Implements the ``ToolCallInterceptor`` protocol from
    ``langchain_mcp_adapters.interceptors``.

    Args:
        max_response_size: Maximum characters for text content in a single
            tool response. Defaults to 20000 (~5K tokens, enough for useful
            content without bloating context).

    Example:
        >>> truncator = ResponseTruncator(max_response_size=20_000)
        >>> provider = MCPProvider(
        ...     server_names=["toolbox"],
        ...     tool_interceptors=[truncator],
        ... )
    """

    def __init__(self, max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE) -> None:
        self.max_response_size = max_response_size

    async def __call__(
        self,
        request: MCPToolCallRequest,
        handler: Callable[[MCPToolCallRequest], Awaitable[_HandlerResult]],
    ) -> _HandlerResult:
        """Intercept tool response and truncate if needed.

        Only truncates ``CallToolResult`` responses.  ``ToolMessage`` and
        ``Command`` results are passed through unchanged.

        Args:
            request: MCPToolCallRequest from the interceptor chain.
            handler: Next handler in the chain (executes the actual tool).

        Returns:
            CallToolResult with text content truncated if over limit,
            or the original result if it is not a CallToolResult.
        """
        result = await handler(request)

        # Only intercept raw MCP CallToolResult — pass through
        # LangGraph-level wrappers unchanged.
        if not isinstance(result, CallToolResult):
            return result

        # Log ALL tool responses (not just oversized) for observability
        text_blocks = [c for c in result.content if isinstance(c, TextContent)]
        total_chars = sum(len(b.text) for b in text_blocks)
        logger.info(f"Tool '{request.name}' response: {total_chars} chars, isError={result.isError}")

        return self._truncate(result)

    def _truncate(self, result: CallToolResult) -> CallToolResult:
        """Truncate text content with smart boundary detection.

        Finds the last paragraph break (``\\n\\n``), sentence end (``. ``),
        or newline before the limit. Falls back to hard cut at limit.
        """
        text_blocks = [c for c in result.content if isinstance(c, TextContent)]
        total_chars = sum(len(b.text) for b in text_blocks)

        if total_chars <= self.max_response_size:
            return result

        new_content: list[Any] = []
        for block in result.content:
            if not isinstance(block, TextContent):
                new_content.append(block)
                continue

            if len(block.text) <= self.max_response_size:
                new_content.append(block)
                continue

            truncated = block.text[: self.max_response_size]
            # Find a clean boundary in the second half of the allowed text
            boundary = max(
                truncated.rfind("\n\n"),
                truncated.rfind(". "),
                truncated.rfind("\n"),
            )
            if boundary > self.max_response_size // 2:
                truncated = truncated[: boundary + 1]

            truncated += f"\n\n[...truncated from {len(block.text):,} chars]"
            new_content.append(TextContent(type="text", text=truncated))

        return CallToolResult(
            content=new_content,
            isError=result.isError,
        )
