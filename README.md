<div align="center">

# WhaAgent

**Production-grade multi-tenant WhatsApp AI platform**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Go 1.21+](https://img.shields.io/badge/go-1.21%2B-00ADD8?style=for-the-badge&logo=go&logoColor=white)](https://go.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-FF0000?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![License](https://img.shields.io/github/license/MusadiqUrRahman/whaagent?style=for-the-badge)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/MusadiqUrRahman/whaagent/ci.yml?style=for-the-badge&logo=github&label=Build)](https://github.com/MusadiqUrRahman/whaagent/actions)

</div>

---

WhaAgent connects AI agents to WhatsApp. Multiple numbers, multiple tenants, single deployment. Go gateway for protocol reliability, Python for agent flexibility, LangGraph for reasoning orchestration.

---

## Architecture

```mermaid
flowchart LR
    subgraph WhatsApp["WhatsApp Network"]
        direction TB
        U1["User A"]
        U2["User B"]
        U3["User C"]
    end

    subgraph Gateway["Go Gateway · whatsmeow"]
        direction TB
        SM["Session Manager<br/>Multi-tenant"]
        QR["QR Stream<br/>SSE"]
        EH["Event Handler<br/>Async"]
    end

    subgraph API["Python API · FastAPI"]
        direction TB
        WH["Webhook Router"]
        AP["Agent Pool<br/>LRU Eviction"]
        CK["Checkpoint<br/>SQLite"]
    end

    subgraph Agents["Agent Layer · LangGraph"]
        direction TB
        R["Router Node<br/>Intent Classification"]
        S["Summarize Node<br/>Context Compression"]
        A["Agent Node<br/>Tool Orchestration"]
    end

    subgraph Tools["Tool Ecosystem"]
        direction TB
        LT["Local Tools"]
        MCP["MCP Servers"]
        EXT["External APIs"]
    end

    subgraph LLM["LLM Providers"]
        direction TB
        OAI["OpenAI"]
        ANT["Anthropic"]
        GGL["Google"]
        OTH["10+ Providers"]
    end

    U1 & U2 & U3 -->|"WhatsApp Protocol"| SM
    SM --> EH
    EH --> WH
    QR -.->|"Scan to link"| WhatsApp

    WH --> AP
    AP --> CK
    CK --> S
    S --> R
    R --> A
    A --> LT & MCP & EXT
    A --> OAI & ANT & GGL & OTH

    style WhatsApp fill:#25D366,color:#fff
    style Gateway fill:#00ADD8,color:#fff
    style API fill:#3776AB,color:#fff
    style Agents fill:#9945FF,color:#fff
    style Tools fill:#FF6B35,color:#fff
    style LLM fill:#E91E63,color:#fff
```

---

## System Design

### Go Gateway

Built on [whatsmeow](https://github.com/tulir/whatsmeow) for direct WhatsApp protocol access.

- **Multi-tenant session management** — concurrent connections for multiple phone numbers
- **LID-based JID resolution** — handles WhatsApp's Linked Identity Device format
- **Async event pipeline** — long LLM calls don't block incoming message processing
- **Persistent typing indicators** — re-sent every 3s during agent inference
- **Session recovery** — survives restarts via device reuse

### Python API

FastAPI server with dependency injection and async request handling.

- **Tenant agent pool** — LRU eviction, per-tenant isolated instances
- **SSE QR streaming** — real-time QR code delivery to browser
- **API key authentication** — gateway-to-API security
- **Health/readiness endpoints** — Kubernetes-ready probes
- **Checkpoint persistence** — SQLite-backed conversation memory

### Agent Framework

LangGraph-powered 3-node state graph.

```
Summarize → Router → Agent
```

- **Summarize node** — token threshold check, compresses old messages to ~128 tokens
- **Router node** — LLM-classified intent (chat, tool_use, research, delegate)
- **Agent node** — tool orchestration, sub-agent delegation, ReAct loop

### Tool Ecosystem

| Layer | Tools |
|-------|-------|
| **Local** | File operations, AST parsing, code search (ripgrep), syntax validation (tree-sitter) |
| **MCP** | Model Context Protocol servers — web fetch, flight search, custom tools |
| **Agent Invocation** | Cross-agent delegation with isolated execution contexts |

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Gateway | Go + whatsmeow | WhatsApp protocol, session management |
| API | FastAPI + uvicorn | Async HTTP server, webhook handling |
| Agents | LangGraph + LangChain | State graph, tool orchestration, memory |
| Tools | tree-sitter, ripgrep | Code analysis, search |
| MCP | Model Context Protocol | External tool integration |
| Storage | SQLite | Checkpoint persistence, tenant data |
| LLM | 10+ providers | OpenAI, Anthropic, Google, Ollama, etc. |
| Testing | pytest + mypy + ruff | 80% coverage, strict types, lint |

---

## Code Quality

- **Type-safe** — strict mypy checking, full type hints across all modules
- **Tested** — 80% coverage, unit + integration tests
- **Linted** — ruff for style, mypy for types
- **Async-first** — non-blocking I/O throughout
- **Error handling** — graceful degradation, circuit breakers for external services

---

## Project Structure

```
whaagent/
├── src/whaagent/
│   ├── agents/              # Agent implementations
│   │   ├── assistant.py     # General-purpose orchestrator
│   │   ├── developer.py     # Code exploration
│   │   ├── news.py          # News aggregation
│   │   └── ...
│   ├── api/
│   │   ├── server.py        # FastAPI app factory
│   │   ├── pool.py          # Tenant agent pool (LRU)
│   │   └── routes/          # REST endpoints
│   ├── graph.py             # 3-node StateGraph
│   ├── agent.py             # AgentBase class
│   ├── mcp/                 # MCP integration
│   │   ├── provider.py      # Connection management
│   │   └── config.py        # Server discovery
│   ├── tools/               # Built-in tools
│   │   ├── codebase_explorer.py
│   │   ├── code_searcher.py
│   │   └── manifest.py      # Tool manifest + circuit breaker
│   ├── llm/                 # LLM abstraction
│   │   └── providers.py     # 10+ provider factories
│   ├── prompts/             # System prompts (.md)
│   └── storage/             # SQLite persistence
├── gateway/                 # Go WhatsApp gateway
│   ├── main.go
│   ├── session.go           # Multi-tenant sessions
│   ├── message.go           # Message handling
│   └── qr.go                # QR code generation
└── tests/                   # Test suite
```

---

## Deployment

```bash
# Docker
docker compose up -d

# Bare metal
uv sync && make gateway-build
whaagent serve &
cd gateway && go run . &
```

---

## License

MIT

---

<div align="center">

[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://python.langchain.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-FF0000?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![Go](https://img.shields.io/badge/Go-00ADD8?style=for-the-badge&logo=go&logoColor=white)](https://go.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![MCP](https://img.shields.io/badge/MCP-4B32C3?style=for-the-badge)](https://modelcontextprotocol.io)

</div>
