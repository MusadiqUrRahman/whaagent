"""Central MCP server configuration.

Single source of truth for all MCP servers. Which agent may use which servers
is defined in AgentRegistry.register(..., mcp_servers=...).
"""

import os
from pathlib import Path
from typing import Any, Dict, cast

import yaml

# All available MCP servers. Each entry must include "transport".
# Resolved at runtime via get_mcp_servers_config() (e.g. env vars for API keys).
# The toolbox URL can be overridden via TOOLBOX_URL environment variable.
DEFAULT_MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    "kiwi-com-flight-search": {
        "url": "https://mcp.kiwi.com",
        "transport": "sse",
    },
    "fetch": {
        "url": "https://remote.mcpservers.org/fetch/mcp",
        "transport": "http",
    },
    "toolbox": {
        "url": "$_TOOLBOX_URL",
        "transport": "sse",
    },
    # Removed: web-forager (now in toolbox as web_search, web_fetch)
    # Removed: hacker-news (now in toolbox as hacker_news_top, hacker_news_item)
}

# Default toolbox URL, can be overridden by TOOLBOX_URL env var
DEFAULT_TOOLBOX_URL = "http://localhost:8080/sse"


def load_yaml_config() -> Dict[str, Dict[str, Any]]:
    """Load MCP server config from mcp_servers.yaml if it exists."""
    config_path = Path("mcp_servers.yaml")
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                content = yaml.safe_load(f) or {}
                return cast(Dict[str, Dict[str, Any]], content.get("mcpServers", {}))
        except Exception as e:
            print(f"Warning: Failed to load {config_path}: {e}")
    return {}


def get_mcp_servers_config(
    override: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Return MCP server config for MultiServerMCPClient.

    Merges DEFAULT_MCP_SERVERS with mcp_servers.yaml and optional override.
    """
    base = {k: dict(v) for k, v in DEFAULT_MCP_SERVERS.items()}
    yaml_config = load_yaml_config()

    # Merge YAML config
    for k, v in yaml_config.items():
        base[k] = dict(base.get(k, {}))
        base[k].update(v)
        if "transport" not in base[k] and "command" in base[k]:
            base[k]["transport"] = "stdio"

    # Merge overrides
    if override:
        for k, v in override.items():
            base[k] = dict(base.get(k, {}))
            base[k].update(v)

    return {k: _resolve_server_config(k, v) for k, v in base.items()}


def _resolve_server_config(server_name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of server config with env-dependent values resolved."""
    cfg = dict(raw)

    # Resolve env variables for MCP server URLs (e.g., $_TOOLBOX_URL)
    if "url" in cfg and isinstance(cfg["url"], str) and cfg["url"].startswith("$_"):
        env_var = cfg["url"][2:]
        cfg["url"] = os.environ.get(env_var, "")

        # Special handling for TOOLBOX_URL with default fallback
        if env_var == "TOOLBOX_URL" and not cfg["url"]:
            cfg["url"] = DEFAULT_TOOLBOX_URL

    # Resolve env variables for MCP server env blocks
    if "env" in cfg and isinstance(cfg["env"], dict):
        for key, value in cfg["env"].items():
            if isinstance(value, str) and value.startswith("$_"):
                env_var_name = value[2:]
                cfg["env"][key] = os.environ.get(env_var_name, "")

    return cfg
