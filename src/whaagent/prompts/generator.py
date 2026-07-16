"""Dynamic prompt generation with tool documentation."""

import logging
from typing import Any

from whaagent.prompts.loader import load_prompt
from whaagent.tools.manifest import ToolManifest

logger = logging.getLogger(__name__)


def generate_tools_section(
    manifest: ToolManifest,
    categories: list[str] | None = None,
) -> str:
    """Generate markdown documentation for tools.

    Args:
        manifest: Tool manifest with all available tools.
        categories: Optional filter for specific categories. None = all.

    Returns:
        Markdown string documenting the tools.
    """
    if categories is not None:
        tools = []
        for cat in categories:
            tools.extend(manifest.get_tools_by_category(cat))
    else:
        tools = manifest.tools

    if not tools:
        return ""

    # Group by category
    tools_by_category: dict[str, list[Any]] = {}
    for tool in tools:
        if tool.category not in tools_by_category:
            tools_by_category[tool.category] = []
        tools_by_category[tool.category].append(tool)

    # Generate markdown
    lines = ["## AVAILABLE TOOLS\n"]
    lines.append("The following tools are available via the toolbox MCP server:\n")

    for category in sorted(tools_by_category.keys()):
        lines.append(f"\n### {category.title()} Tools\n")
        for tool in tools_by_category[category]:
            lines.append(f"- **{tool.name}** - {tool.description}")

    lines.append("\n\n## USAGE NOTES\n")
    lines.append("- All tools are accessed via the toolbox MCP server\n")
    lines.append("- Use tools proactively when they would help complete the task\n")
    lines.append("- If unsure which tool to use, describe what you need\n")

    return "\n".join(lines)


def generate_system_prompt(
    manifest: ToolManifest,
    categories: list[str] | None = None,
    base_prompt: str | None = None,
    agent_name: str | None = None,
) -> str:
    """Generate system prompt with tool documentation.

    Args:
        manifest: Tool manifest with all available tools.
        categories: Optional filter for specific tool categories.
        base_prompt: Pre-loaded prompt string. If None, loads from agent_name.
        agent_name: Name of the agent (fallback for loading base prompt).

    Returns:
        Complete system prompt with tool documentation.
    """
    if base_prompt is None:
        if agent_name is None:
            raise ValueError("Either base_prompt or agent_name must be provided")
        base_prompt = load_prompt(agent_name)
    tools_section = generate_tools_section(manifest, categories)

    if tools_section:
        return f"{base_prompt}\n\n{tools_section}"

    return base_prompt
