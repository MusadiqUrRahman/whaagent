#!/usr/bin/env python3
"""Test MCP server connectivity.

This script tests connections to all configured MCP servers and provides
detailed diagnostic information. It can be run from within Docker to
verify that MCP servers are accessible.

Usage:
    # From host machine
    python scripts/test_mcp_connectivity.py

    # From within Docker container
    python /app/scripts/test_mcp_connectivity.py
"""

import asyncio
import logging
import socket
import ssl
import sys
from typing import Any
from urllib.parse import urlparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_dns_resolution(hostname: str) -> dict[str, str]:
    """Test DNS resolution for a hostname.

    Args:
        hostname: The hostname to resolve.

    Returns:
        Dictionary with DNS resolution results.
    """
    result = {"hostname": hostname, "success": False, "ip_address": None, "error": None}
    
    try:
        logger.info(f"  Testing DNS resolution for {hostname}...")
        ip_address = socket.gethostbyname(hostname)
        result["success"] = True
        result["ip_address"] = ip_address
        logger.info(f"  ✓ DNS resolution successful: {hostname} → {ip_address}")
    except socket.gaierror as e:
        result["error"] = str(e)
        logger.error(f"  ✗ DNS resolution failed for {hostname}: {e}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"  ✗ Unexpected DNS error for {hostname}: {e}")
    
    return result


async def test_ssl_connection(hostname: str, port: int = 443) -> dict[str, str]:
    """Test SSL/TLS connection to a host.

    Args:
        hostname: The hostname to connect to.
        port: The port to connect to (default: 443).

    Returns:
        Dictionary with SSL connection results.
    """
    result = {
        "hostname": hostname,
        "port": port,
        "success": False,
        "certificate": None,
        "error": None,
    }

    try:
        logger.info(f"  Testing SSL/TLS connection to {hostname}:{port}...")
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                result["success"] = True
                result["certificate"] = {
                    "subject": cert.get("subject"),
                    "issuer": cert.get("issuer"),
                    "notAfter": cert.get("notAfter"),
                }
                logger.info(f"  ✓ SSL/TLS connection successful to {hostname}:{port}")
    except ssl.SSLError as e:
        result["error"] = f"SSL/TLS error: {e}"
        logger.error(f"  ✗ SSL/TLS error for {hostname}:{port}: {e}")
    except socket.timeout:
        result["error"] = "Connection timeout"
        logger.error(f"  ✗ Connection timeout to {hostname}:{port}")
    except ConnectionRefusedError:
        result["error"] = "Connection refused"
        logger.error(f"  ✗ Connection refused by {hostname}:{port}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"  ✗ Unexpected error connecting to {hostname}:{port}: {e}")

    return result


async def test_http_url(url: str) -> dict[str, str]:
    """Test HTTP/HTTPS connectivity to a URL.

    Args:
        url: The URL to test.

    Returns:
        Dictionary with HTTP connection results.
    """
    result = {"url": url, "success": False, "status_code": None, "error": None}

    try:
        import httpx

        logger.info(f"  Testing HTTP connection to {url}...")
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            result["success"] = True
            result["status_code"] = response.status_code
            logger.info(f"  ✓ HTTP connection successful: {url} → {response.status_code}")
    except httpx.TimeoutException as e:
        result["error"] = f"Timeout: {e}"
        logger.error(f"  ✗ HTTP timeout for {url}: {e}")
    except httpx.ConnectError as e:
        result["error"] = f"Connection error: {e}"
        logger.error(f"  ✗ HTTP connection error for {url}: {e}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"  ✗ Unexpected HTTP error for {url}: {e}")

    return result


async def test_mcp_server(server_name: str, config: dict[str, str]) -> dict[str, Any]:
    """Test connectivity to an MCP server.

    Args:
        server_name: The name of the MCP server.
        config: The server configuration (must include 'url' and 'transport').

    Returns:
        Dictionary with comprehensive test results.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing MCP server: {server_name}")
    logger.info(f"{'='*60}")

    results = {
        "server_name": server_name,
        "config": config,
        "dns": None,
        "ssl": None,
        "http": None,
        "mcp_connection": None,
    }

    url = config.get("url")
    transport = config.get("transport")

    if not url:
        logger.error(f"  ✗ No URL configured for {server_name}")
        return results

    # Parse URL
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    port = parsed_url.port or (443 if parsed_url.scheme in ("https", "wss") else 80)

    logger.info(f"URL: {url}")
    logger.info(f"Transport: {transport}")
    logger.info(f"Hostname: {hostname}")
    logger.info(f"Port: {port}")

    # Test DNS resolution
    if hostname:
        results["dns"] = await test_dns_resolution(hostname)

    # Test SSL/TLS for HTTPS endpoints
    if parsed_url.scheme in ("https", "wss") and hostname:
        results["ssl"] = await test_ssl_connection(hostname, port)

    # Test HTTP connectivity
    if parsed_url.scheme in ("http", "https"):
        results["http"] = await test_http_url(url)

    # Test actual MCP connection
    try:
        logger.info(f"  Testing MCP protocol connection...")
        from whaagent.mcp import MCPProvider

        provider = MCPProvider(server_names=[server_name])
        tools = await provider.get_tools()
        results["mcp_connection"] = {
            "success": True,
            "tools_count": len(tools),
            "tools": [tool.name for tool in tools],
        }
        logger.info(f"  ✓ MCP connection successful: {len(tools)} tools loaded")
    except Exception as e:
        results["mcp_connection"] = {"success": False, "error": str(e)}
        logger.error(f"  ✗ MCP connection failed: {e}")

    return results


async def main() -> None:
    """Main test function."""
    logger.info("\n" + "=" * 60)
    logger.info("MCP Server Connectivity Test")
    logger.info("=" * 60)

    # Get MCP server configurations
    try:
        from whaagent.mcp.config import get_mcp_servers_config

        server_configs = get_mcp_servers_config()
        logger.info(f"\nFound {len(server_configs)} configured MCP servers:")
        for name in server_configs:
            logger.info(f"  - {name}: {server_configs[name].get('url', 'no URL')}")
    except Exception as e:
        logger.error(f"Failed to load MCP server configurations: {e}")
        sys.exit(1)

    # Test each server
    all_results = {}
    for server_name, config in server_configs.items():
        results = await test_mcp_server(server_name, config)
        all_results[server_name] = results

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    successful = []
    failed = []

    for server_name, results in all_results.items():
        mcp_conn = results.get("mcp_connection", {})
        if mcp_conn and mcp_conn.get("success"):
            successful.append(server_name)
            tools_count = mcp_conn.get("tools_count", 0)
            logger.info(f"✓ {server_name}: {tools_count} tools loaded")
        else:
            failed.append(server_name)
            error = mcp_conn.get("error", "Unknown error") if mcp_conn else "No connection"
            logger.info(f"✗ {server_name}: {error}")

            # Show diagnostic details
            if results.get("dns") and not results["dns"].get("success"):
                logger.info(f"  → DNS failed: {results['dns'].get('error')}")
            if results.get("ssl") and not results["ssl"].get("success"):
                logger.info(f"  → SSL failed: {results['ssl'].get('error')}")
            if results.get("http") and not results["http"].get("success"):
                logger.info(f"  → HTTP failed: {results['http'].get('error')}")

    logger.info("\n" + "=" * 60)
    logger.info(f"Total: {len(server_configs)} servers")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    logger.info("=" * 60)

    if failed:
        logger.error("\nFailed servers detected. Check the logs above for details.")
        logger.error("\nCommon issues and solutions:")
        logger.error("  1. DNS resolution failed:")
        logger.error("     - Check DNS configuration in docker-compose.yml")
        logger.error("     - Ensure container has network access")
        logger.error("  2. SSL/TLS errors:")
        logger.error("     - Ensure SSL certificates are installed in container")
        logger.error("     - Check for proxy or firewall interference")
        logger.error("  3. Connection timeouts:")
        logger.error("     - Check network connectivity")
        logger.error("     - Verify server is accessible from container")
        logger.error("  4. Connection refused:")
        logger.error("     - Verify server URL and port are correct")
        logger.error("     - Check if server is running")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(0)