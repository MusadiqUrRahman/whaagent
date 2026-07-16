# WhatsApp Multi-Tenant Integration

whaagent provides a production-ready WhatsApp integration with Go gateway for reliable session management and Python API for flexible agent execution.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  WhatsApp App   │────▶│   Go Gateway     │────▶│   Python API    │
│  (your phone)   │     │  (whatsmeow)     │     │  (FastAPI)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                          │
                               │                          ▼
                               │                   ┌─────────────────┐
                               │                   │   LLM Provider  │
                               │                   │  (Claude, GPT)  │
                               │                   └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  QR Codes        │
                        │  SSE Stream      │
                        └──────────────────┘
```

**Key Features:**
- **Multi-tenant**: Support multiple WhatsApp accounts (phone numbers) in a single deployment
- **Session persistence**: WhatsApp sessions survive gateway restarts
- **Async message handling**: Long LLM calls don't block WhatsApp event processing
- **Typing indicator persistence**: Keeps "typing..." visible during long LLM responses
- **Progress logging**: INFO-level status updates while waiting for LLM responses
- **LID-based JID support**: Handles WhatsApp's Linked Identity Device format for "note to self" messages

## Installation

### Requirements

- Go 1.21+
- Python 3.12+
- `uv` package manager
- ffmpeg (for audio transcription, if needed)

### Setup

```bash
# Clone the repository
git clone https://github.com/jeancsil/whaagent.git
cd whaagent

# Install Python dependencies
uv sync

# Build Go gateway
make gateway-build
```

## Configuration

Create `.whaagent.yaml`:

```yaml
llm:
  provider: anthropic  # or openai, google, ollama, etc.
  model: claude-sonnet-4-6
  temperature: 0.7

api:
  host: 127.0.0.1
  port: 8000

storage:
  base_path: ~/.local/share/whaagent

logging:
  level: INFO
  api_log: logs/api.log
  whatsapp_log: logs/whatsapp.log

auth:
  api_keys:
    "admin-key-123": "admin"
    "test-key-456": "test"

whatsapp:
  tenants:
    - id: personal
      phone: "REDACTED_PHONE"
      default_agent: developer
      allowed_contacts: []
    - id: work
      phone: "+15551234567"
      default_agent: committer
      allowed_contacts:
        - "+15559876543"
```

**Configuration Options:**

| Option | Description |
|--------|-------------|
| `tenants[].id` | Unique tenant identifier |
| `tenants[].phone` | Phone number in E.164 format |
| `tenants[].default_agent` | Agent to use for messages from this tenant |
| `tenants[].allowed_contacts` | Optional whitelist of allowed phone numbers (empty = all) |
| `auth.api_keys` | API keys for gateway-to-API communication |

## Usage

### Start the Services

```bash
# Terminal 1: Start Python API
whaagent serve

# Terminal 2: Start Go Gateway
cd gateway
go run .
```

Or use Docker:

```bash
docker compose up -d
```

### Authenticate with WhatsApp

1. Open the QR code page in your browser:
   ```bash
   open http://localhost:8000/api/v1/whatsapp/qr/personal/page
   ```

2. Scan the QR code with WhatsApp:
   - Open WhatsApp on your phone
   - Go to Settings > Linked Devices
   - Link a Device

3. Wait for connection confirmation (check logs or the SSE stream)

### Send Messages

Send a message to yourself on WhatsApp ("note to self" chat):

```
You: What's the weather like today?
Agent: [Typing indicator appears and persists during LLM call...]
Agent: I'll check the current weather for you...
```

The typing indicator will stay visible during long LLM responses, and progress logging keeps you informed in the gateway logs.

### Monitor Logs

```bash
# Python API logs
tail -f logs/api.log

# Go Gateway logs
tail -f logs/whatsapp.log
```

## API Endpoints

### WhatsApp Gateway → Python API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/channels/whatsapp/message` | Forward incoming message |
| `POST` | `/api/v1/whatsapp/qr/{tenant_id}` | QR code from gateway |
| `POST` | `/api/v1/whatsapp/status/{tenant_id}` | Connection status update |

### Client → Gateway (for monitoring)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/whatsapp/qr/{tenant_id}` | SSE stream for QR codes |
| `GET` | `/api/v1/whatsapp/qr/{tenant_id}/page` | HTML QR code viewer |

### Python API (Agent Execution)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/agents` | List available agents |
| `POST` | `/api/v1/agents/{name}/run` | Execute agent |

## Troubleshooting

### "Node handling took" warning

**Fixed:** Message handling is now async, so this warning no longer appears even during 90+ second LLM calls.

### Typing indicator disappears during long responses

**Fixed:** The typing indicator now re-sends every 3 seconds, keeping it visible throughout the LLM response.

### "Self-message phone number mismatch"

**Fixed:** The gateway now supports LID-based JIDs (Linked Identity Device format) that WhatsApp uses for "note to self" messages.

### No response after sending message

Check the logs:
```bash
tail -f logs/whatsapp.log | grep -E "Processing|Forwarding|Still waiting|completed"
```

You should see:
- `Processing self-message` — Message received
- `Forwarding message to Python API` — LLM call started
- `Still waiting for LLM response` — Progress updates (every 15s)
- `LLM response received` — LLM finished
- `Message processing completed` — Response sent to WhatsApp

### QR code not appearing

1. Check that the Python API is running: `curl http://localhost:8000/health`
2. Check gateway logs for errors
3. Ensure the tenant ID in the URL matches your config

### Connection drops

The gateway now reuses existing device sessions across restarts. If you still experience drops:
- Check internet connection
- WhatsApp may rate-limit new connections
- Try re-authenticating with a new QR code

## Go Gateway Internals

### Message Processing Flow

1. **WhatsApp Event** → `handleEvent` (async dispatch)
2. **Self-Message Detection** → `isSelfMessage` (JID matching)
3. **Typing Indicator** → Goroutine with 3s refresh
4. **API Forwarding** → `forwardToPythonAPI` with progress logging
5. **Response** → `sendResponseToWhatsApp`
6. **Cleanup** → Typing indicator stopped

### Self-Message Detection

The gateway uses a multi-strategy approach to detect "note to self" messages:

1. **Exact JID match**: `Chat == Sender` (same User and Server)
2. **Store.ID match**: Chat matches the authenticated device's phone-based JID
3. **Store.LID match**: Chat matches the device's LID (for LID-only messages)
4. **Phone number fallback**: Normalized phone comparison against tenant config

This handles all WhatsApp JID formats:
- Phone-based: `34677427318@s.whatsapp.net`
- LID-based: `118657162162293@lid`
- Mixed: Chat uses LID, Sender uses phone

### Progress Logging

During LLM calls, the gateway logs:
- `Forwarding message to Python API (waiting for LLM response)` — Start
- `Still waiting for LLM response (elapsed=15s)` — Every 15 seconds
- `LLM response received (elapsed=91s)` — Done
- `Message processing completed (elapsed=91.5s, response_len=234)` — Final

## See Also

- [Multi-Tenant Architecture](../README.md#multi-tenant-whatsapp-architecture) — Architecture overview
- [Configuration](../configuration.md) — Full configuration reference
- [LLM Providers](../llm/providers.md) — Supported LLM providers
- [MCP Servers](../mcp/servers.md) — Extending with MCP
