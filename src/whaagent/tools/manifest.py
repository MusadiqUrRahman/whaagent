"""Tool manifest client for discovering toolbox capabilities."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5  # Open circuit after N failures
    success_threshold: int = 2  # Close circuit after N successes in half-open
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=60))  # Time before half-open
    initial_backoff: timedelta = field(default_factory=lambda: timedelta(seconds=1))
    max_backoff: timedelta = field(default_factory=lambda: timedelta(seconds=30))


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures."""

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._last_attempt_time: datetime | None = None

    def _calculate_backoff(self) -> float:
        """Calculate exponential backoff time in seconds."""
        if self._last_attempt_time is None:
            return 0.0

        # Exponential backoff with jitter
        initial_secs = float(self._config.initial_backoff.total_seconds())
        max_secs = float(self._config.max_backoff.total_seconds())
        base_backoff = min(initial_secs * (2.0**self._failure_count), max_secs)
        return float(base_backoff)

    def allow_request(self) -> bool:
        """Check if request should be allowed based on circuit state."""
        now = datetime.now()

        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            # Check if we should transition to half-open
            if self._last_failure_time and (now - self._last_failure_time) >= self._config.timeout:
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                self._state = CircuitBreakerState.HALF_OPEN
                self._success_count = 0
                return True
            return False

        # HALF_OPEN state - allow requests to test recovery
        return True

    def record_success(self) -> None:
        """Record a successful request."""
        self._last_attempt_time = datetime.now()

        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._config.success_threshold:
                logger.info("Circuit breaker closing after successful recovery")
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        elif self._state == CircuitBreakerState.CLOSED:
            # Reset failure count on success in closed state
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed request."""
        self._last_attempt_time = datetime.now()
        self._last_failure_time = datetime.now()
        self._failure_count += 1

        if self._state == CircuitBreakerState.HALF_OPEN:
            # Immediately return to open on failure in half-open
            logger.warning("Circuit breaker returning to OPEN after half-open failure")
            self._state = CircuitBreakerState.OPEN
        elif self._failure_count >= self._config.failure_threshold:
            logger.warning(
                f"Circuit breaker opening after {self._failure_count} failures "
                f"(threshold: {self._config.failure_threshold})"
            )
            self._state = CircuitBreakerState.OPEN

    async def wait_for_backoff(self) -> None:
        """Wait based on exponential backoff if needed."""
        backoff = self._calculate_backoff()
        if backoff > 0:
            logger.debug(f"Circuit breaker: waiting {backoff:.1f}s before retry")
            await asyncio.sleep(backoff)


class ToolInfo(BaseModel):
    """Information about a single tool."""

    name: str
    category: str
    description: str
    parameters: dict[str, Any] | None = None
    examples: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Validate that tool name is not empty."""
        assert v, "Tool name cannot be empty"
        return v


class ToolManifest(BaseModel):
    """Complete tool manifest from toolbox server."""

    version: str = "1.0.0"
    tools: list[ToolInfo]

    def get_tools_by_category(self, category: str) -> list[ToolInfo]:
        """Get all tools in a category."""
        return [t for t in self.tools if t.category == category]

    def get_tool(self, name: str) -> ToolInfo | None:
        """Get a tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def get_categories(self) -> list[str]:
        """Get all unique categories."""
        return sorted(set(t.category for t in self.tools))


@dataclass
class CachedManifest:
    """Cached manifest with expiry."""

    manifest: ToolManifest
    fetched_at: datetime
    ttl: timedelta

    def is_fresh(self) -> bool:
        """Check if cache is still valid."""
        return datetime.now() < self.fetched_at + self.ttl


class ToolManifestClient:
    """Client for fetching and caching tool manifests with circuit breaker."""

    DEFAULT_TTL = timedelta(minutes=5)
    DEFAULT_TIMEOUT = 10.0  # seconds

    def __init__(
        self,
        toolbox_url: str,
        ttl: timedelta | None = None,
        timeout: float | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize the tool manifest client.

        Args:
            toolbox_url: Base URL of the toolbox server.
            ttl: Cache time-to-live for manifests.
            timeout: HTTP request timeout in seconds.
            circuit_breaker_config: Optional circuit breaker configuration.
        """
        # Strip transport-specific paths (/sse, /messages) to get the base URL.
        # The toolbox_url config often includes the MCP transport path (e.g., http://host:8080/sse)
        # but the manifest REST API lives at the base URL (/api/manifest).
        base_url = toolbox_url.rstrip("/")
        for suffix in ("/sse", "/messages"):
            if base_url.endswith(suffix):
                base_url = base_url[: -len(suffix)]
        self.toolbox_url = base_url.rstrip("/")
        self.ttl = ttl or self.DEFAULT_TTL
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._cache: CachedManifest | None = None

        # Load circuit breaker config from environment and create CircuitBreaker instance
        cb_config = self._load_env_config(circuit_breaker_config)
        self._circuit_breaker = CircuitBreaker(cb_config)

    def _load_env_config(self, base_config: CircuitBreakerConfig | None) -> CircuitBreakerConfig:
        """Load circuit breaker configuration from environment variables."""
        import os

        config_dict: dict[str, Any] = {}

        if failure_threshold := os.environ.get("MANIFEST_CB_FAILURE_THRESHOLD"):
            config_dict["failure_threshold"] = int(failure_threshold)
        if timeout_val := os.environ.get("MANIFEST_CB_TIMEOUT"):
            config_dict["timeout"] = timedelta(seconds=int(timeout_val))
        if initial_backoff := os.environ.get("MANIFEST_CB_INITIAL_BACKOFF"):
            config_dict["initial_backoff"] = timedelta(seconds=float(initial_backoff))
        if max_backoff := os.environ.get("MANIFEST_CB_MAX_BACKOFF"):
            config_dict["max_backoff"] = timedelta(seconds=float(max_backoff))

        if base_config:
            # Start with base config and override with env vars
            base_fields = {
                "failure_threshold": base_config.failure_threshold,
                "success_threshold": base_config.success_threshold,
                "timeout": base_config.timeout,
                "initial_backoff": base_config.initial_backoff,
                "max_backoff": base_config.max_backoff,
            }
            config_dict = {**base_fields, **config_dict}

        return CircuitBreakerConfig(**config_dict) if config_dict else (base_config or CircuitBreakerConfig())

    async def fetch_manifest(self) -> ToolManifest:
        """Fetch fresh manifest from toolbox server with circuit breaker."""
        # Check circuit breaker before attempting request
        if not self._circuit_breaker.allow_request():
            backoff = self._circuit_breaker._calculate_backoff()
            raise ConnectionError(
                f"Circuit breaker is OPEN: toolbox server at {self.toolbox_url} is currently unavailable. "
                f"Will retry after {backoff:.1f}s."
            )

        # Wait for backoff if needed
        await self._circuit_breaker.wait_for_backoff()

        url = f"{self.toolbox_url}/api/manifest"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Parse the ToolManifest JSON response
                manifest = ToolManifest(**response.json())

                # Record success
                self._circuit_breaker.record_success()
                return manifest

        except httpx.HTTPError as e:
            self._circuit_breaker.record_failure()
            raise ConnectionError(f"Failed to fetch manifest from toolbox: {e}") from e
        except Exception:
            self._circuit_breaker.record_failure()
            raise

    async def get_manifest(self, force_refresh: bool = False) -> ToolManifest:
        """Get manifest, using cache if fresh."""
        if not force_refresh and self._cache and self._cache.is_fresh():
            return self._cache.manifest

        try:
            manifest = await self.fetch_manifest()
            self._cache = CachedManifest(
                manifest=manifest,
                fetched_at=datetime.now(),
                ttl=self.ttl,
            )
            return manifest
        except ConnectionError as e:
            # If circuit breaker is preventing requests, try to return stale cache
            if self._cache:
                logger.warning(f"Using stale manifest cache due to circuit breaker: {e}")
                return self._cache.manifest
            raise

    def clear_cache(self) -> None:
        """Clear the cached manifest."""
        self._cache = None

    @property
    def circuit_breaker_state(self) -> CircuitBreakerState:
        """Get the current circuit breaker state."""
        return self._circuit_breaker._state
