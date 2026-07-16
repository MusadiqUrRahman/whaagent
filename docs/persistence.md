# Agent Memory Persistence

whaagent agents support persistent conversation memory using `langgraph-checkpoint-sqlite`. This allows agents to maintain context across process restarts and share memory between different interfaces (like CLI and WhatsApp).

## How it Works

whaagent uses [LangGraph's SqliteSaver](https://langchain-ai.github.io/langgraph/how-tos/persistence/) to store checkpoints of the agent's state in a SQLite database. The `thread_id` is used to identify and isolate different conversations.

In the WhatsApp integration, the `sender_id` (phone number) is used as the `thread_id`, ensuring each user has their own persistent history.

## Configuration

Persistence is enabled by providing a `checkpointer` to the `AgentBase` class.

### 1. Centralized Storage (`whaagent.storage`)

The `whaagent.storage` module provides a centralized way to manage the SQLite database and checkpointers.

```python
from whaagent.storage.database import Database
from whaagent.agent import AgentBase

# Initialize database
db = Database(Path("path/to/storage.db"))

# Get an async checkpointer (recommended for web/messaging apps)
async with db.get_checkpointer(is_async=True) as checkpointer:
    agent = MyAgent(thread_id="unique-user-id", checkpointer=checkpointer)
    response = await agent.run("Hello!")
```

### 2. WhatsApp Persistence

The `WhatsAppRouterAgent` automatically initializes persistence using the `storage.db` file in the configured storage path. 

When a user sends a message, their conversation history is loaded from the database, and any new interactions are saved back.

## Development and Testing

To test persistence locally, you can use the integration tests provided in `tests/storage/test_persistence_integration.py`.

### Requirements

Persistence requires the `langgraph-checkpoint-sqlite` package, which is included in the project dependencies.

```bash
pip install langgraph-checkpoint-sqlite
```

If you are using `AsyncSqliteSaver`, `aiosqlite` is also required.
