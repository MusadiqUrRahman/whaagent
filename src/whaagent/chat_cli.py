"""Chat CLI module with MCP subprocess management and tenant utilities."""

import atexit
import logging
import os
import subprocess
import time
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()  # must load .env before reading whaagent_TOOLKIT_PATH

from whaagent.config import whaagentConfig, WhatsAppTenantConfig, get_config  # noqa: E402

logger = logging.getLogger(__name__)
console = Console()

# Module-level constants
TEST_TENANT_ID = "test"
TEST_TENANT_PHONE = "+1555000000"
TEST_API_KEY = "test-secret"
DEFAULT_TOOLBOX_PORT = 8080
MCP_STARTUP_TIMEOUT = 15


def configure_chat_logging(level: str) -> None:
    """Configure logging for the chat CLI.

    Args:
        level: Logging level (e.g., 'WARNING', 'DEBUG').
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="[%X]",
        handlers=[logging.StreamHandler()],
        force=True,
    )


def send_chat_message(
    message: str,
    config: whaagentConfig | None = None,
    agent_name: str | None = None,
    thread_id: str | None = None,
) -> dict[str, str]:
    """Send a test message through the WhatsApp webhook route via TestClient.

    This function creates a TestClient that calls the real FastAPI route handler
    for the WhatsApp webhook. It's primarily used for testing and CLI chat.

    Args:
        message: The message to send.
        config: Configuration to use. If None, calls get_config().
        agent_name: Optional agent name to use instead of the tenant's default.
        thread_id: Optional thread ID (currently unused, reserved for future).

    Returns:
        A dict with 'response' and 'tenant_id' keys.

    Raises:
        RuntimeError: If the webhook returns a non-200 status code.
    """
    # Get config if not provided
    if config is None:
        config = get_config()

    # Find the test tenant
    tenant = find_test_tenant(config)

    # Temporarily override default_agent if agent_name is provided
    original_agent = tenant.default_agent
    try:
        if agent_name is not None:
            tenant.default_agent = agent_name

        # Import here to avoid circular imports
        from fastapi.testclient import TestClient

        from whaagent.api.pool import TenantAgentPool
        from whaagent.api.server import create_app

        # Create test client
        app = create_app()

        # Initialize agent pool (normally done in lifespan, but TestClient doesn't run lifespan)
        if not hasattr(app.state, "agent_pool"):
            app.state.agent_pool = TenantAgentPool(max_size=10)

        client = TestClient(app)

        # Prepare request body
        body: dict[str, str] = {
            "from": tenant.phone,
            "message": message,
            "tenant_id": tenant.id,
        }

        # Send POST request with API key header
        response = client.post(
            "/api/v1/channels/whatsapp/message",
            headers={"X-API-Key": TEST_API_KEY},
            json=body,
        )

        # Check for errors
        if response.status_code != 200:
            detail = response.json().get("detail", "Unknown error")
            raise RuntimeError(f"Webhook failed with status {response.status_code}: {detail}")

        # Cast the response to the expected type
        result: dict[str, str] = response.json()
        return result

    finally:
        # Restore original agent
        if agent_name is not None:
            tenant.default_agent = original_agent


class MCPServerManager:
    """Manages MCP toolkit subprocess lifecycle.

    This class handles starting and stopping the agentic_toolkit MCP server
    as a subprocess. It reads the toolkit path from the whaagent_TOOLKIT_PATH
    environment variable and manages the process lifecycle including cleanup
    on exit.
    """

    def __init__(self) -> None:
        """Initialize MCPServerManager with no running process."""
        self.process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        """Start the MCP toolkit subprocess if configured.

        Reads whaagent_TOOLKIT_PATH from environment. If set and path exists,
        starts 'uv run python -m agentic_toolkit' as a subprocess with
        start_new_session=True. Registers stop() with atexit for cleanup.

        If path is not set, logs info and returns.
        If path doesn't exist, logs warning and returns.
        """
        toolkit_path = os.getenv("whaagent_TOOLKIT_PATH")

        if not toolkit_path:
            logger.info("whaagent_TOOLKIT_PATH not set, skipping MCP toolkit startup")
            return

        if not Path(toolkit_path).exists():
            logger.warning(
                "whaagent_TOOLKIT_PATH '%s' does not exist, skipping MCP toolkit startup",
                toolkit_path,
            )
            return

        logger.info("Starting MCP toolkit from %s", toolkit_path)

        # Start the subprocess with a new process group
        self.process = subprocess.Popen(
            ["uv", "run", "python", "-m", "agentic_toolkit"],
            cwd=toolkit_path,
            start_new_session=True,
        )

        logger.info("MCP toolkit started with PID %d", self.process.pid)

        # Register cleanup handler
        atexit.register(self.stop)

    def stop(self) -> None:
        """Stop the MCP toolkit subprocess.

        Safely terminates the subprocess with a 5-second timeout.
        Falls back to kill() on timeout.
        Falls back to os.killpg on OSError (e.g., process already terminated).

        Safe to call when process is None (no-op).
        """
        if self.process is None:
            return

        try:
            self.process.terminate()
            self.process.wait(timeout=5)
            logger.info("MCP toolkit stopped gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("MCP toolkit did not terminate gracefully, force killing")
            self.process.kill()
            self.process.wait(timeout=5)
        except OSError:
            # Process may have already terminated
            # Use process group kill as fallback
            if self.process.pid:
                try:
                    os.killpg(os.getpgid(self.process.pid), 9)  # SIGKILL
                    logger.info("MCP toolkit killed via process group")
                except (ProcessLookupError, OSError) as e:
                    logger.debug("Process group kill failed (process likely gone): %s", e)

        self.process = None


def find_test_tenant(config: whaagentConfig | None = None) -> WhatsAppTenantConfig:
    """Find the test tenant from configuration.

    Searches config.whatsapp.tenants for a tenant with id == "test".
    Returns a default WhatsAppTenantConfig if not found.

    Args:
        config: Configuration to search. If None, calls get_config().

    Returns:
        The test tenant configuration, either from config or a default.
    """
    if config is None:
        config = get_config()

    # Search for test tenant
    for tenant in config.whatsapp.tenants:
        if tenant.id == TEST_TENANT_ID:
            return tenant

    # Return default test tenant
    return WhatsAppTenantConfig(
        id=TEST_TENANT_ID,
        phone=TEST_TENANT_PHONE,
        default_agent="assistant",
        allowed_contacts=[TEST_TENANT_PHONE],
    )


def chat_command(
    message: str = typer.Argument(..., help="Message to send to the agent."),
    thread_id: str | None = typer.Option(None, "--thread-id", "-t", help="Thread ID to continue."),
    agent_name: str | None = typer.Option(None, "--agent", "-a", help="Agent name (default: from tenant config)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug output."),
) -> None:
    """Send a test message through the WhatsApp pipeline locally."""
    # Configure logging based on verbose flag
    configure_chat_logging("DEBUG" if verbose else "WARNING")

    # Track start time
    start_time = time.time()

    # Create MCP server manager
    mcp_manager = MCPServerManager()

    try:
        # Start MCP servers
        mcp_manager.start()

        # Find test tenant for display
        tenant = find_test_tenant()

        # Print agent and thread info
        display_agent = agent_name or tenant.default_agent
        console.print(f"[bold cyan]Agent:[/bold cyan] {display_agent}")
        console.print(f"[bold cyan]Thread:[/bold cyan] {thread_id or 'auto-generated'}")
        console.print()

        # Send the message
        result = send_chat_message(message=message, agent_name=agent_name)

        # Print the response
        console.print()
        console.print("[bold green]Response:[/bold green]")
        console.print(result.get("response", "No response"))

        # Print elapsed time
        elapsed = time.time() - start_time
        console.print()
        console.print(f"[dim][Completed in {elapsed:.1f}s][/dim]")

    except Exception as e:
        # Print error in red
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    finally:
        # Always stop MCP manager
        mcp_manager.stop()
