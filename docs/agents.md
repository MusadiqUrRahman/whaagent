# Available Agents

This document provides detailed information about all available agents in the whaagent framework.

## Agent Overview

| Agent | Purpose | MCP Servers | Local Tools |
|-------|---------|-------------|-------------|
| `developer` | **Code Master:** Read, search & edit code. | `webfetch` | All codebase tools |
| `travel-coordinator` | **Trip Planner:** Orchestrates agents. | `kiwi-com-flight-search`, `webfetch` | Uses 3 sub-agents |
| `chef` | **Chef:** Recipes from your fridge. | `webfetch` | - |
| `news` | **News Anchor:** Aggregates top stories. | `webfetch` | - |
| `travel` | **Flight Booker:** Finds the best routes. | `kiwi-com-flight-search` | - |
| `simple` | **Chat Buddy:** Vanilla conversational agent. | - | - |
| `github-pr-reviewer` | **PR Reviewer:** Reviews diffs, posts inline comments & summaries. | - | Custom GitHub tools |
| `whatsapp` | **WhatsApp Agent:** Bidirectional WhatsApp communication (personal account) with slash commands. | `webfetch`, `duckduckgo-search` | - |

---

## Developer Agent

**Purpose:** The developer agent is a code master designed to read, search, and edit codebases.

### Capabilities

- **Codebase Exploration:** Navigate and understand project structures
- **Code Search:** Fast pattern matching using ripgrep
- **File Editing:** Safe modifications to source files
- **AST Analysis:** Understand code signatures in multiple languages

### MCP Servers
- `webfetch` - For fetching documentation and web resources

### Local Tools
- All available codebase tools (see [tools.md](tools.md) for details)

### Usage Example
```bash
bin/whaagent.sh developer -i "Explain the architecture of this project"
bin/whaagent.sh developer -i "Find all functions that use the database connection"
```

---

## Travel Coordinator Agent

**Purpose:** Orchestrates multiple agents to plan complex trips.

### Capabilities

- Coordinates with `travel` and `chef` sub-agents
- Manages complex travel planning workflows
- Integrates flight search with dining recommendations

### MCP Servers
- `kiwi-com-flight-search` - Real-time flight data
- `webfetch` - For travel-related web content

### Architecture
Uses 3 specialized sub-agents working together via LangGraph.

### Usage Example
```bash
bin/whaagent.sh travel-coordinator -i "Plan a weekend trip from Madrid to Paris"
```

---

## Chef Agent

**Purpose:** Suggests recipes based on ingredients you have available.

### Capabilities

- Recipe suggestions based on available ingredients
- Fetches recipes from online sources
- Adapts recipes to your ingredient constraints

### MCP Servers
- `webfetch` - For fetching recipe information

### Usage Example
```bash
bin/whaagent.sh chef -i "I have chicken, rice, and soy sauce. What can I make?"
```

---

## News Agent

**Purpose:** Aggregates and summarizes top news stories.

### Capabilities

- Fetches latest news from multiple sources
- Summarizes key developments
- Filters by topics when requested

### MCP Servers
- `webfetch` - For fetching news content

### Usage Example
```bash
bin/whaagent.sh news -i "What are today's top tech stories?"
```

---

## Travel Agent

**Purpose:** Finds the best flight routes for your journey.

### Capabilities

- Real-time flight search
- Route optimization
- Price comparison

### MCP Servers
- `kiwi-com-flight-search` - Real-time flight data

### Usage Example
```bash
bin/whaagent.sh travel -i "Find flights from Madrid to Barcelona next weekend"
```

---

## Simple Agent

**Purpose:** A basic conversational agent for general chatting.

### Capabilities

- Natural conversation
- General knowledge (via LLM)
- No specialized tools

### MCP Servers
- None

### Usage Example
```bash
bin/whaagent.sh simple -i "Tell me a joke"
```

---

## GitHub PR Reviewer Agent

**Purpose:** Automatically reviews pull requests by analyzing diffs and posting comments.

### Capabilities

- **Diff Analysis:** Reviews code changes line by line
- **Inline Comments:** Posts specific feedback on problematic code
- **Summary Comments:** Provides overall PR assessment
- **Thread Responses:** Engages in review conversations

### Local Tools
- `get_pr_diff` - Retrieve the pull request diff
- `get_pr_comments` - Get existing comments on a PR
- `post_review_comment` - Post inline review comments
- `post_general_comment` - Post overall PR feedback
- `reply_to_review_comment` - Reply to review comment threads
- `get_pr_metadata` - Fetch PR metadata (title, author, etc.)

### Usage Example
```bash
bin/whaagent.sh github-pr-reviewer -i "Review PR #123 for bugs and style issues"
```

---

## WhatsApp Agent

The WhatsApp agent enables bidirectional communication through your personal WhatsApp account using QR code authentication.

### Requirements
- Go 1.21+ and Git (for WhatsApp backend)
- Python 3.13+
- A configured LLM provider

### Configuration

```bash
# 1. Copy example config
cp whaagent/config/whatsapp.yaml.example whaagent/config/whatsapp.yaml

# 2. Edit config/whatsapp.yaml with your settings:
# - model: "claude-sonnet-4-6"  # Your LLM model
# - privacy.allowed_contact: "+34 666 666 666"  # Your phone number (only this number can interact)
# - channel.storage_path: "~/storage/whatsapp"  # Where to store session data
# - mcp_servers: ["web-fetch", "duckduckgo-search"]  # Optional: MCP servers to use
```

### Usage

```bash
# Start the WhatsApp agent
bin/whaagent.sh whatsapp --config config/whatsapp.yaml

# With custom settings (overrides config file)
bin/whaagent.sh whatsapp --allowed-contact "+1234567890" --storage ~/custom/path

# Customize MCP servers
bin/whaagent.sh whatsapp --mcp-servers "web-fetch,duckduckgo-search"
bin/whaagent.sh whatsapp --mcp-servers none  # Disable MCP

# Verbose mode for debugging
bin/whaagent.sh whatsapp --verbose
```

### First Run
1. Scan the QR code displayed in your terminal
2. Wait for WhatsApp to authenticate
3. Send a message from your configured phone number
4. Agent will respond automatically

### Privacy & Security
- 🔒 Only processes messages from the configured contact
- 🔒 Group chat messages are automatically filtered (not sent to LLM)
- 🔒 All data stored locally (no cloud storage of conversations)
- 🔒 Messages from other contacts are silently ignored
- 🔒 Message deduplication prevents reprocessing

### Configuration Options
| Option | Description |
|--------|-------------|
| `model` | LLM model to use (defaults to provider default) |
| `mcp_servers` | MCP servers for web search and content fetching |
| `privacy.allowed_contact` | Only this phone number can interact with the agent |
| `privacy.log_filtered_messages` | Log filtered messages for debugging |
| `channel.storage_path` | Directory for WhatsApp session and database files |
| `features.group_messages` | Currently disabled by default for privacy |

### MCP Servers
- `webfetch` - For fetching web content
- `duckduckgo-search` - For web search capabilities

### Slash Commands

The WhatsApp agent uses a router architecture that responds to special command prefixes, providing different modes of interaction:

| Command | Description |
|---------|-------------|
| `/learn <topic>` | **Learning Mode:** Get step-by-step tutorials and detailed explanations. The agent breaks down complex topics into clear, logical steps with practical examples. |
| `<any message>` | **Default Mode:** General assistant with web search and chat capabilities. |

#### Learning Mode (`/learn`)

Use the `/learn` command when you want in-depth tutorials and explanations on any topic:

```
You: /learn how to build a REST API with Python

Agent: *Here's a step-by-step tutorial on building a REST API with Python:*

1. **Choose a Framework** - Flask or FastAPI are popular options
2. **Install Dependencies** - `pip install flask`
3. [continues with detailed steps...]
```

The learning mode is designed for education, providing:
- Structured, step-by-step breakdowns
- Clear explanations of technical terms
- Practical examples and analogies
- Encouraging and patient communication style

#### Default Mode

For quick questions, web searches, or general conversation, just send a message without any command prefix:

```
You: What's the weather like in Madrid?

Agent: I'll check the current weather in Madrid for you...
[uses web search to fetch and summarize current conditions]
```

---

## Creating Custom Agents

To create your own agent, see the [Build Your Own Agent](../README.md#️-build-your-own-agent) section in the main README.
