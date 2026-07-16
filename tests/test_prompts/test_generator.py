"""Tests for dynamic prompt generator."""


class TestGenerateToolsSection:
    """Tests for generate_tools_section."""

    def test_generates_markdown_for_tools(self) -> None:
        """Should generate markdown documentation for tools."""
        from whaagent.prompts.generator import generate_tools_section
        from whaagent.tools.manifest import ToolInfo, ToolManifest

        manifest = ToolManifest(
            tools=[
                ToolInfo(name="web_search", category="web", description="Search the web"),
                ToolInfo(name="web_fetch", category="web", description="Fetch URL content"),
                ToolInfo(name="git_status", category="git", description="Get git status"),
            ]
        )

        result = generate_tools_section(manifest)

        assert "AVAILABLE TOOLS" in result
        assert "web_search" in result
        assert "web_fetch" in result
        assert "git_status" in result

    def test_filters_by_categories(self) -> None:
        """Should filter tools by category when specified."""
        from whaagent.prompts.generator import generate_tools_section
        from whaagent.tools.manifest import ToolInfo, ToolManifest

        manifest = ToolManifest(
            tools=[
                ToolInfo(name="web_search", category="web", description="Search"),
                ToolInfo(name="git_status", category="git", description="Status"),
            ]
        )

        result = generate_tools_section(manifest, categories=["web"])

        assert "web_search" in result
        assert "git_status" not in result

    def test_empty_categories_list_returns_empty(self) -> None:
        """Should return empty when categories list is empty."""
        from whaagent.prompts.generator import generate_tools_section
        from whaagent.tools.manifest import ToolInfo, ToolManifest

        manifest = ToolManifest(
            tools=[
                ToolInfo(name="web_search", category="web", description="Search"),
            ]
        )
        result = generate_tools_section(manifest, categories=[])
        assert result == ""


class TestGenerateSystemPrompt:
    """Tests for generate_system_prompt."""

    def test_combines_base_with_tools(self) -> None:
        """Should combine base prompt with tools section."""
        from whaagent.prompts.generator import generate_system_prompt
        from whaagent.tools.manifest import ToolInfo, ToolManifest

        manifest = ToolManifest(
            tools=[
                ToolInfo(name="web_search", category="web", description="Search"),
            ]
        )

        result = generate_system_prompt(
            manifest=manifest,
            categories=["web"],
            agent_name="learning",
        )

        assert "expert educator" in result.lower()  # From base prompt
        assert "web_search" in result  # From tools section

    def test_accepts_base_prompt_directly(self) -> None:
        """Should use provided base_prompt instead of loading from agent_name."""
        from whaagent.prompts.generator import generate_system_prompt
        from whaagent.tools.manifest import ToolInfo, ToolManifest

        manifest = ToolManifest(
            tools=[
                ToolInfo(name="web_search", category="web", description="Search"),
            ]
        )

        result = generate_system_prompt(
            manifest=manifest,
            categories=["web"],
            base_prompt="You are a custom agent.",
        )

        assert "custom agent" in result
        assert "web_search" in result
