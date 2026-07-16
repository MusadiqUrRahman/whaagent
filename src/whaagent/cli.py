"""CLI for whaagent - An agentic framework for building AI-powered applications."""

import asyncio
import logging
import traceback
from typing import Any, Callable, Type

import typer
from rich.console import Console

from whaagent.chat_cli import chat_command
from whaagent.cli_init import init_command
from whaagent.config import get_config
from whaagent.mcp import MCPConnectionError, MCPProvider
from whaagent.registry import AgentRegistry

RUN_TIMEOUT_SECONDS = 600

app = typer.Typer(
    name="whaagent",
    help="A CLI for running agents in whaagent.",
    add_completion=True,
)
console = Console()
logger = logging.getLogger(__name__)


def configure_logging(verbose: bool) -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level="DEBUG" if verbose else "INFO",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="[%X]",
        handlers=[
            logging.StreamHandler(),  # Output to console
        ],
        force=True,
    )


def _print_chained_causes(error: BaseException) -> None:
    """Print chained exception causes recursively."""
    exc_ptr: BaseException | None = error
    while exc_ptr is not None:
        chained_cause: BaseException | None = getattr(exc_ptr, "__cause__", None) or getattr(
            exc_ptr, "__context__", None
        )
        if chained_cause is None:
            break
        console.print(f"[red]  cause: {chained_cause}[/red]")
        exc_ptr = chained_cause


def _handle_mcp_connection_error(error: MCPConnectionError) -> None:
    """Handle MCP connection errors with helpful suggestions."""
    console.print(f"[bold red]MCP Connectivity Error:[/bold red] {error}")
    cause = error.cause

    if hasattr(cause, "exceptions"):
        for idx, sub_error in enumerate(cause.exceptions):
            console.print(f"[red]  sub-exception {idx + 1}: {sub_error}[/red]")
    elif error.__cause__:
        console.print(f"[red]  cause: {error.__cause__}[/red]")

    console.print("[yellow]Suggestion:[/yellow] Ensure that MCP server URL is correct and you have network access.")
    if "fetch" in error.server_name:
        console.print("[yellow]Note:[/yellow] fetch requires a valid remote URL. Check mcp/config.py")


async def _run_agent(
    agent_cls: Type[Any],
    input_text: str,
    allowed_mcp: list[str] | None,
    agent_name: str,
) -> str:
    """Run an agent with optional MCP tools."""
    tool_categories = AgentRegistry.get_tool_categories(agent_name)

    if allowed_mcp:
        provider = MCPProvider(server_names=allowed_mcp)
        async with provider.tool_session() as mcp_tools:
            agent = agent_cls(
                initial_mcp_tools=mcp_tools,
                _agent_name=agent_name,
                tool_categories=tool_categories,
            )
            return str(await agent.run(input_text))

    agent = agent_cls(_agent_name=agent_name, tool_categories=tool_categories)
    return str(await agent.run(input_text))


def execute_agent(agent_name: str, input_text: str, timeout_sec: int) -> str:
    """Execute an agent with the given input.

    Args:
        agent_name: Name of the agent to run.
        input_text: Input text for the agent.
        timeout_sec: Maximum runtime in seconds.

    Returns:
        The agent's response string.

    Raises:
        typer.Exit: If agent is not found.
        TimeoutError: If agent execution times out.
    """
    agent_cls = AgentRegistry.get(agent_name)
    if not agent_cls:
        raise typer.Exit(code=1)

    allowed_mcp = AgentRegistry.get_mcp_servers(agent_name)
    try:
        return asyncio.run(
            asyncio.wait_for(
                _run_agent(agent_cls, input_text, allowed_mcp, agent_name),
                timeout=float(timeout_sec),
            ),
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"Run timed out after {timeout_sec}s.") from exc


@app.command(name="list")
def list_agents() -> None:
    """List all available agents."""
    AgentRegistry.discover_agents()
    agents = AgentRegistry.list_agents()
    console.print(f"[bold magenta]Available Agents:[/bold magenta] {', '.join(agents)}\n")


@app.command(name="info")
def agent_info(
    agent_name: str = typer.Argument(..., help="Name of the agent to inspect."),
) -> None:
    """Show detailed information about an agent."""
    agent_cls = AgentRegistry.get(agent_name)
    if not agent_cls:
        console.print(f"[bold red]Error:[/bold red] Agent '{agent_name}' not found.")
        console.print("[yellow]Tip:[/yellow] Use 'list' command to see all available agents.")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]Agent Details:[/bold cyan] {agent_name}\n")

    # Agent class name
    console.print(f"[bold]Class:[/bold] {agent_cls.__name__}")

    # Module
    console.print(f"[bold]Module:[/bold] {agent_cls.__module__}")

    # MCP servers
    mcp_servers = AgentRegistry.get_mcp_servers(agent_name)
    if mcp_servers is None:
        console.print("[bold]MCP Servers:[/bold] None (no MCP access)")
    elif mcp_servers:
        console.print(f"[bold]MCP Servers:[/bold] {', '.join(mcp_servers)}")
    else:
        console.print("[bold]MCP Servers:[/bold] (configured but empty list)")

    # Tool categories
    tool_categories = AgentRegistry.get_tool_categories(agent_name)
    if tool_categories:
        console.print(f"[bold]Tool Categories:[/bold] {', '.join(tool_categories)}")

    # Create agent instance first (needed for system prompt and tools)
    agent = None
    try:
        agent = agent_cls(initial_mcp_tools=[])  # type: ignore[call-arg]
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Could not instantiate agent: {e}")

    # System prompt (if available) - need to instantiate to access property
    console.print("\n[bold]System Prompt:[/bold]")
    if agent and hasattr(agent, "system_prompt"):
        try:
            system_prompt = agent.system_prompt
            console.print(system_prompt)
        except Exception as e:
            console.print(f"[dim](Could not access system prompt: {e})[/dim]")
    else:
        console.print("[dim](No system prompt defined)[/dim]")

    # Tools info
    console.print("\n[bold]Tools:[/bold]")
    if agent:
        try:
            tools = agent.get_tools()

            if not tools:
                console.print("  No tools configured")
            else:
                for tool in tools:
                    tool_name = getattr(tool, "name", tool.__class__.__name__)
                    tool_desc = getattr(tool, "description", "(no description)")
                    console.print(f"  - [green]{tool_name}[/green]: {tool_desc}")
        except Exception as e:
            console.print(f"  [dim](Could not list tools: {e})[/dim]")
    else:
        console.print("  [dim](Could not instantiate agent to list tools)[/dim]")


@app.command(name="config")
def show_config() -> None:
    """Show the current configuration."""
    config = get_config()

    console.print("[bold cyan]whaagent Configuration:[/bold cyan]\n")

    console.print("[bold]LLM:[/bold]")
    console.print(f"  Provider: {config.llm.provider or 'auto-detected'}")
    console.print(f"  Model: {config.llm.model or 'default'}")
    console.print(f"  Temperature: {config.llm.temperature}")
    if config.llm.max_tokens:
        console.print(f"  Max Tokens: {config.llm.max_tokens}")

    console.print("\n[bold]Logging:[/bold]")
    console.print(f"  Level: {config.logging.level}")
    if config.logging.file:
        console.print(f"  File: {config.logging.file}")
    if config.logging.directory:
        console.print(f"  Directory: {config.logging.directory}")

    console.print("\n[bold]MCP:[/bold]")
    console.print(f"  Servers: {', '.join(config.mcp.servers.keys()) if config.mcp.servers else 'default'}")

    console.print("\n[bold]Agents:[/bold]")
    if config.agents.prompts_dir:
        console.print(f"  Prompts Directory: {config.agents.prompts_dir}")
    else:
        console.print("  Prompts Directory: bundled")

    if config._config_path:
        console.print(f"\n[dim]Config file: {config._config_path}[/dim]")
    else:
        console.print("\n[dim]Config file: not found (using defaults)[/dim]")


app.command(name="init")(init_command)


def create_agent_command(agent_name: str) -> Callable[[str, int], None]:
    """Create a typer command for running an agent.

    Args:
        agent_name: Name of the agent.

    Returns:
        A typer command function.
    """

    def command(
        input_text: str = typer.Option(..., "--input", "-i", help="Input text for the agent."),
        timeout_sec: int = typer.Option(
            RUN_TIMEOUT_SECONDS,
            "--timeout",
            "-t",
            help="Max run time in seconds (MCP + LLM + tools).",
        ),
    ) -> None:
        """Run an agent."""
        if not AgentRegistry.get(agent_name):
            console.print(f"[bold red]Error:[/bold red] Agent '{agent_name}' not found.")
            raise typer.Exit(code=1)

        console.print(f"[bold blue]Running agent:[/bold blue] {agent_name}...")

        try:
            result = execute_agent(agent_name=agent_name, input_text=input_text, timeout_sec=timeout_sec)
            console.print(f"[bold green]Result from {agent_name}:[/bold green]")
            console.print(result)
        except typer.Exit:
            raise
        except TimeoutError as error:
            console.print(
                "[bold red]Error running agent:[/bold red] "
                f"{error} Check MCP server connectivity or use --timeout to increase."
            )
            raise typer.Exit(code=1)
        except MCPConnectionError as error:
            _handle_mcp_connection_error(error)
            raise typer.Exit(code=1)
        except Exception as error:
            console.print(f"[bold red]Error running agent:[/bold red] {error}")
            _print_chained_causes(error)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                console.print("[dim]" + traceback.format_exc() + "[/dim]")
            else:
                console.print("[dim]Run with --verbose to see full traceback.[/dim]")
            raise typer.Exit(code=1)

    command.__doc__ = f"Run the {agent_name} agent."
    return command


# Discover and register agents
AgentRegistry.discover_agents()

# Create dynamic commands for each agent (excluding whatsapp-messenger which has a custom command)
for _name in AgentRegistry.list_agents():
    app.command(name=_name)(create_agent_command(_name))


# Register the chat command
app.command(name="chat")(chat_command)


@app.command(name="serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Server host"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
) -> None:
    """Start the REST API server."""
    from whaagent.api.server import run_server
    from whaagent.config import get_config

    config = get_config()
    if host != "127.0.0.1":
        config.api.host = host
    if port != 8000:
        config.api.port = port

    console.print(f"[bold green]Starting whaagent API server on {config.api.host}:{config.api.port}[/bold green]")
    run_server()


@app.callback(invoke_without_command=True)
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """whaagent CLI."""
    configure_logging(verbose)
    logging.info("Starting CLI")

    if app.registered_commands is None:
        console.print("[bold yellow]No command provided. Use --help to see available commands.[/bold yellow]")


if __name__ == "__main__":
    app()
