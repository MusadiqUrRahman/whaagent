# Built-in Agents

whaagent includes 5 pre-configured agents for common use cases.

## Developer Agent

**Name:** `developer`
**Purpose:** Code exploration, analysis, and editing

### Capabilities
- Search codebases with ripgrep
- Explore project structure
- Read and edit files
- Validate syntax

### Tools
- `code_searcher` - Ripgrep-based code search
- `file_finder` - Find files by pattern
- `structure_explorer` - Explore directory structure
- `file_outliner` - Get file overview
- `file_fragment_reader` - Read file sections
- `file_editor` - Edit files safely

### MCP Servers
- `fetch` - Fetch web content

### Usage

```bash
# CLI
whaagent developer -i "Explain the authentication system"

# Python
from whaagent import AgentRegistry
agent = AgentRegistry.get("developer")()
result = await agent.run("Find all database queries")
```

### Prompt

Located at `whaagent/prompts/developer.md`. Customize by:
1. Creating `./prompts/developer.md`
2. Or setting `agents.prompts.developer` in config

---

## GitHub PR Reviewer Agent

**Name:** `github-pr-reviewer`
**Purpose:** Automated PR review with inline comments

### Capabilities
- Analyze PR diffs
- Post inline review comments
- Provide summary feedback
- Respond to review threads

### Tools
- `get_pr_diff` - Retrieve PR diff
- `get_pr_comments` - Get existing comments
- `post_review_comment` - Post inline comments
- `post_general_comment` - Post overall feedback
- `reply_to_review_comment` - Reply to threads
- `get_pr_metadata` - Fetch PR metadata

### MCP Servers
- None (uses local tools only)

### Usage

```bash
whaagent github-pr-reviewer -i "Review PR #123 for bugs"
```

### Prompt

Located at `whaagent/prompts/github_pr_reviewer.md`.

---

## Learning Agent

**Name:** `learning`
**Purpose:** Educational tutorials and explanations

### Capabilities
- Create step-by-step tutorials
- Explain complex concepts
- Fetch educational resources
- Search for examples

### Tools
- None (uses MCP only)

### MCP Servers
- `fetch` - Fetch web content
- `web-forager` - Web search

### Usage

```bash
whaagent learning -i "Teach me about Python async/await"
```

### Prompt

Located at `whaagent/prompts/learning.md`.

---

## News Agent

**Name:** `news`
**Purpose:** News aggregation and summarization

### Capabilities
- Fetch latest news
- Summarize articles
- Filter by topic
- Compare sources

### Tools
- None (uses MCP only)

### MCP Servers
- `fetch` - Fetch news content
- `web-forager` - Search for news

### Usage

```bash
whaagent news -i "What are today's top AI stories?"
```

### Prompt

Located at `whaagent/prompts/news.md`.

---

## YouTube Agent

**Name:** `youtube`
**Purpose:** Video transcript analysis

### Capabilities
- Extract video transcripts
- Summarize video content
- Answer questions about videos
- Cache transcripts locally

### Tools
- `youtube_transcript` - Extract video transcripts

### MCP Servers
- None

### Usage

```bash
# With video ID
whaagent youtube -i "Summarize video dQw4w9WgXcQ"

# With URL
whaagent youtube -i "What's this video about: https://youtube.com/watch?v=dQw4w9WgXcQ"
```

### Prompt

Located at `whaagent/prompts/youtube.md`.

### Transcript Cache

Transcripts are cached locally for faster repeated access:
- Location: `~/.whaagent/youtube_cache/`
- Format: JSON with metadata
- Auto-expires after 30 days

---

## Customizing Built-in Agents

### Override Prompts

Create a custom prompt file:

```bash
mkdir -p ./prompts
cat > ./prompts/developer.md << 'EOF'
You are an expert Python developer specializing in Django.
Focus on security best practices and performance optimization.
EOF
```

Or use config:

```yaml
# .whaagent.yaml
agents:
  prompts:
    developer: |
      You are a security-focused code reviewer.
      Always check for OWASP Top 10 vulnerabilities.
```

### Extend an Agent

```python
from whaagent.agents import DeveloperAgent
from whaagent import AgentRegistry

@AgentRegistry.register("security-reviewer")
class SecurityReviewerAgent(DeveloperAgent):
    @property
    def system_prompt(self) -> str:
        base = super().system_prompt
        return f"{base}\n\nFocus on security vulnerabilities."
```

## See Also

- [Custom Agents](custom.md) - Create your own
- [Prompts](prompts.md) - Manage prompts
- [Tools](../tools/index.md) - Available tools
