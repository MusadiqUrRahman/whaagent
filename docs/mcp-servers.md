# MCP Servers

This document provides detailed information about the MCP (Model Context Protocol) servers available in the Agentic Framework.

## Server Overview

| Server | Purpose | API Key Needed? |
|--------|---------|-----------------|
| `kiwi-com-flight-search` | Search real-time flights | 🟢 No |
| `webfetch` | Extract clean text from URLs & web search | 🟢 No |
| `duckduckgo-search` | Web search via DuckDuckGo | 🟢 No |

---

## kiwi-com-flight-search

Real-time flight search integration using the Kiwi.com API.

### Description
Provides access to live flight data including prices, schedules, and routing information. Used by the `travel` and `travel-coordinator` agents.

### Capabilities
- Search flights between cities
- Get real-time pricing
- Compare different routes
- Find optimal travel dates

### Example Usage
```python
# The travel agent automatically uses this server when querying flights
# Example agent input:
# "Find flights from Madrid to Barcelona for next weekend"
```

### Configuration
No API key required. The server connects directly to Kiwi.com's public API.

---

## webfetch

Fetches and extracts clean text from web pages and performs web searches.

### Description
Retrieves web content and converts it to readable, clean text format. Also supports web search functionality for finding relevant pages.

### Capabilities
- Fetch any URL and extract readable content
- Perform web searches
- Convert HTML to clean markdown/text
- Follow redirects automatically

### Example Usage
```python
# Fetch a specific page
webfetch("https://example.com/article")

# Web search (via the MCP server)
websearch("python best practices 2025")
```

### Configuration
No API key required. Uses publicly available web fetching and search APIs.

---

## duckduckgo-search

Web search integration using DuckDuckGo.

### Description
Provides privacy-focused web search capabilities without tracking.

### Capabilities
- Web search
- Instant answers
- No tracking or personalization
- Anonymous results

### Example Usage
```python
# Perform a web search
duckduckgo_search("latest tech news")

# Search for specific information
duckduckgo_search("how to install python on mac")
```

### Configuration
No API key required. Uses DuckDuckGo's public search API.

---

## Adding Custom MCP Servers

To add a new MCP server to the framework:

### 1. Add Server Configuration

Edit `src/whaagent/mcp/config.py`:

```python
DEFAULT_MCP_SERVERS = {
    "my-server": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-myserver"],
        "env": {
            # Server-specific environment variables
        }
    },
    # ... existing servers
}
```

### 2. Register Server with Agent

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("my-agent", mcp_servers=["my-server"])
class MyAgent(LangGraphMCPAgent):
    @property
    def system_prompt(self) -> str:
        return "You have access to my custom MCP server."
```

### 3. Test the Server

```bash
# Test with your agent
bin/agent.sh my-agent -i "Use my-server to do something"
```

---

## Using MCP Servers in Agents

MCP servers are automatically loaded when specified in the agent registration:

```python
@AgentRegistry.register("my-agent", mcp_servers=["webfetch", "duckduckgo-search"])
class MyAgent(LangGraphMCPAgent):
    # The agent now has access to web fetch and search capabilities
    pass
```

The LLM automatically discovers available tools from the MCP servers and uses them as needed based on the conversation context.
