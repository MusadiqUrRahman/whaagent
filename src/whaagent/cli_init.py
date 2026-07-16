"""Interactive initialization command for whaagent.

Provides `whaagent init` — a first-run wizard that collects mandatory
configuration (LLM provider, API key, model) and writes ~/.whaagent.yaml.
Optionally creates a .env file with the API key.
"""

import shlex
from pathlib import Path
from typing import Any, cast

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()


SUPPORTED_PROVIDERS: dict[str, dict[str, Any]] = {
    "z.ai": {
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "base_url_default": "https://api.z.ai/api/coding/paas/v4",
        "default_model": "glm-4.7",
        "needs_api_key": True,
        "needs_base_url": True,
    },
    "openai": {
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "",
        "base_url_default": "",
        "default_model": "gpt-4o-mini",
        "needs_api_key": True,
        "needs_base_url": False,
    },
    "anthropic": {
        "provider": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "",
        "base_url_default": "",
        "default_model": "claude-sonnet-4-6",
        "needs_api_key": True,
        "needs_base_url": False,
    },
    "google": {
        "provider": "google_genai",
        "api_key_env": "GOOGLE_API_KEY",
        "base_url_env": "",
        "base_url_default": "",
        "default_model": "gemini-2.0-flash",
        "needs_api_key": True,
        "needs_base_url": False,
    },
    "ollama": {
        "provider": "ollama",
        "api_key_env": "",
        "base_url_env": "OLLAMA_BASE_URL",
        "base_url_default": "http://localhost:11434",
        "default_model": "llama3",
        "needs_api_key": False,
        "needs_base_url": True,
    },
    "openrouter": {
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "base_url_default": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4-6",
        "needs_api_key": True,
        "needs_base_url": True,
    },
}


def _get_config_path() -> Path:
    """Return the path where config will be written."""
    return Path.home() / ".whaagent.yaml"


def _get_env_path() -> Path:
    """Return the path where .env will be written."""
    return Path.cwd() / ".env"


def _build_config(
    provider_key: str,
    model: str,
    temperature: float,
    whatsapp_tenant: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the YAML config dictionary.

    Args:
        provider_key: Key in SUPPORTED_PROVIDERS (e.g. "z.ai", "anthropic").
        model: Model name string.
        temperature: Temperature float.
        whatsapp_tenant: Optional dict with id, phone, default_agent keys.

    Returns:
        Config dict ready for YAML serialization.
    """
    provider_info = SUPPORTED_PROVIDERS[provider_key]
    config: dict[str, Any] = {
        "llm": {
            "provider": provider_info["provider"],
            "model": model,
            "temperature": temperature,
        },
        "api": {
            "host": "127.0.0.1",
            "port": 8000,
        },
    }

    if whatsapp_tenant:
        config["whatsapp"] = {
            "tenants": [whatsapp_tenant],
        }

    return config


def _write_config(path: Path, config: dict[str, Any]) -> None:
    """Write config dict to a YAML file."""
    with path.open("w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def _write_env_file(path: Path, env_vars: dict[str, str]) -> None:
    """Append or create .env file with the given environment variables.

    Args:
        path: Path to the .env file.
        env_vars: Dict of env var name to value (e.g. {"OPENAI_API_KEY": "sk-...", "OPENAI_BASE_URL": "https://..."}).
    """
    lines: list[str] = []
    if path.exists():
        lines = path.read_text().splitlines()

    # Remove existing lines for any variable we're about to write
    for var_name in env_vars:
        lines = [line for line in lines if not line.startswith(f"{var_name}=")]

    for var_name, value in env_vars.items():
        lines.append(f"{var_name}={shlex.quote(value)}")

    path.write_text("\n".join(lines) + "\n")


def _print_next_steps(
    provider_key: str,
    wrote_env: bool,
    env_vars: dict[str, str],
    has_whatsapp: bool,
) -> None:
    """Print a Rich panel with next steps."""
    provider_info = SUPPORTED_PROVIDERS[provider_key]
    steps = [
        "[bold green]Configuration saved![/bold green]",
        "",
        "Try it out:",
        "  [cyan]whaagent list[/cyan]                    # list available agents",
        '  [cyan]whaagent chat "Hello!"[/cyan]           # chat with the assistant',
        "",
    ]

    if not wrote_env and provider_info["needs_api_key"]:
        api_key_env = provider_info["api_key_env"]
        steps.extend(
            [
                f"  [yellow]Set your API key:[/yellow] export {api_key_env}='your-key-here'",
                "",
            ]
        )

    if has_whatsapp:
        steps.extend(
            [
                "WhatsApp gateway:",
                "  [cyan]whaagent serve[/cyan]                  # start Python API (port 8000)",
                "  [cyan]./whaagent-gateway[/cyan]              # start Go gateway (other terminal)",
                "  Open http://localhost:8000/api/v1/whatsapp/qr/personal/page",
                "  Scan the QR code with WhatsApp > Linked Devices",
                "",
            ]
        )

    steps.extend(
        [
            "Gateway binary download:",
            "  [link=https://github.com/jeancsil/whaagent/releases]https://github.com/jeancsil/whaagent/releases[/link]",
            "",
            "Full docs: [link=https://github.com/jeancsil/whaagent#readme]README[/link]",
        ]
    )

    console.print(Panel("\n".join(steps), title="Next Steps", border_style="green"))


def init_command() -> None:
    """Interactive setup wizard for whaagent."""
    config_path = _get_config_path()
    env_path = _get_env_path()

    console.print(
        Panel(
            "Welcome to [bold magenta]whaagent[/bold magenta]!\n"
            "This wizard will set up your configuration.\n"
            "Press Enter to accept defaults shown in brackets.",
            title="whaagent Setup",
            border_style="magenta",
        )
    )

    # Check if config already exists
    if config_path.exists():
        if not Confirm.ask(
            f"Config file exists at [cyan]{config_path}[/cyan]. Overwrite?",
            default=False,
        ):
            console.print("[yellow]Setup skipped.[/yellow]")
            return

    # Step 1: Provider
    provider_names = ", ".join(SUPPORTED_PROVIDERS.keys())
    provider_key = ""
    while provider_key not in SUPPORTED_PROVIDERS:
        provider_key = Prompt.ask(
            f"[bold]LLM provider[/bold] ({provider_names})",
            default="z.ai",
        ).lower()
        if provider_key not in SUPPORTED_PROVIDERS:
            console.print(f"[red]Unsupported provider: {provider_key}[/red]")

    provider_info = SUPPORTED_PROVIDERS[provider_key]

    # Step 2: Model
    model = cast(
        str,
        Prompt.ask(
            "[bold]Model name[/bold]",
            default=provider_info["default_model"],
        ),
    )

    # Step 3: Temperature
    temperature = 0.1
    while True:
        temperature_str = Prompt.ask(
            "[bold]Temperature[/bold] (0.0 = deterministic, 1.0 = creative)",
            default="0.1",
        )
        try:
            temperature = float(temperature_str)
            if 0.0 <= temperature <= 2.0:
                break
            console.print("[red]Temperature must be between 0.0 and 2.0[/red]")
        except ValueError:
            console.print(f"[red]Invalid number: {temperature_str}[/red]")

    # Step 4: API key (only if provider needs one)
    wrote_env = False
    env_vars_to_write: dict[str, str] = {}

    if provider_info["needs_api_key"]:
        api_key = cast(
            str,
            Prompt.ask(
                "[bold]API key[/bold] (will be written to .env)",
                default="",
            ),
        )

        if api_key:
            env_vars_to_write[provider_info["api_key_env"]] = api_key

    # Step 5: Base URL (for z.ai, openrouter, ollama — providers with custom endpoints)
    if provider_info["needs_base_url"] and provider_info["base_url_env"]:
        base_url = cast(
            str,
            Prompt.ask(
                "[bold]API base URL[/bold]",
                default=provider_info["base_url_default"],
            ),
        )
        env_vars_to_write[provider_info["base_url_env"]] = base_url

    # Write .env if we have anything to write
    if env_vars_to_write:
        write_env = Confirm.ask(
            f"Write credentials to [cyan]{env_path}[/cyan]?",
            default=True,
        )
        if write_env:
            _write_env_file(env_path, env_vars_to_write)
            wrote_env = True
            for var_name in env_vars_to_write:
                console.print(f"[green]Wrote {var_name} to {env_path}[/green]")
    elif provider_info["needs_api_key"] and not env_vars_to_write:
        console.print(
            f"[yellow]No API key provided. Set {provider_info['api_key_env']} before running agents.[/yellow]"
        )

    # Step 6: WhatsApp tenant (optional)
    whatsapp_tenant: dict[str, str] | None = None
    setup_whatsapp = Confirm.ask(
        "[bold]Set up WhatsApp integration?[/bold] (requires Go gateway binary)",
        default=False,
    )

    if setup_whatsapp:
        tenant_id = cast(
            str,
            Prompt.ask(
                "[bold]Tenant ID[/bold] (a short name, e.g. 'personal')",
                default="personal",
            ),
        )
        phone = cast(
            str,
            Prompt.ask(
                "[bold]WhatsApp phone number[/bold] (international format, e.g. +5511999999999)",
            ),
        )
        default_agent = cast(
            str,
            Prompt.ask(
                "[bold]Default agent[/bold] (assistant, developer, learning, news)",
                default="assistant",
            ),
        )

        whatsapp_tenant = {
            "id": tenant_id,
            "phone": phone,
            "default_agent": default_agent,
        }

    # Write config
    config = _build_config(provider_key, model, temperature, whatsapp_tenant)
    _write_config(config_path, config)
    console.print(f"[green]Config written to {config_path}[/green]")

    # Print next steps
    _print_next_steps(provider_key, wrote_env, env_vars_to_write, whatsapp_tenant is not None)
