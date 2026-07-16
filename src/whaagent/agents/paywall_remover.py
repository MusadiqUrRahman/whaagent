"""Paywall Remover Agent — specialist for extracting paywalled web content.

Uses the DeepScrapeTool's 3-stage pipeline (Crawl4AI → Firecrawl → Archive.ph)
to bypass paywalls, anti-bot protection, and JavaScript rendering barriers.
"""

from typing import Any, Sequence

from whaagent.agent import AgentBase
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry
from whaagent.tools import DeepScrapeTool


@AgentRegistry.register(
    "paywall-remover",
    mcp_servers=["toolbox"],
    tool_categories=["web"],
)
class PaywallRemoverAgent(AgentBase):
    """Specialist agent for extracting content from paywalled/blocked sites.

    Capabilities:
    - Extract full article text from paywalled sites (globo.com, wsj.com, nyt.com, etc.)
    - Bypass Cloudflare/turnstile anti-bot protection
    - Handle JavaScript-rendered content via headless browser (Crawl4AI)
    - Fall back through 3-stage pipeline for maximum coverage

    MCP Servers:
        toolbox: Centralized tool server for web_search as fallback
    """

    @property
    def system_prompt(self) -> str:
        """Return the paywall-remover system prompt."""
        return load_prompt("paywall_remover")

    def local_tools(self) -> Sequence[Any]:
        """Return deep scrape tool."""
        return [DeepScrapeTool().to_langchain_tool()]
