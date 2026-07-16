import re
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """Simple in-memory rate limiter per tenant_id.

    Tracks request counts per tenant_id within sliding time windows.
    """

    max_requests: int = 60  # requests per minute
    window_seconds: int = 60
    _requests: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def is_allowed(self, tenant_id: str) -> bool:
        """Check if request is within rate limit."""
        now = time.time()
        cutoff = now - self.window_seconds
        # Clean old entries
        self._requests[tenant_id] = [t for t in self._requests[tenant_id] if t > cutoff]
        if len(self._requests[tenant_id]) >= self.max_requests:
            return False
        self._requests[tenant_id].append(now)
        return True


def validate_tenant_id(tenant_id: str) -> str:
    """Validate and sanitize tenant_id.

    Args:
        tenant_id: The tenant ID to validate.

    Returns:
        Sanitized tenant_id.

    Raises:
        ValueError: If tenant_id contains invalid characters.
    """
    if not tenant_id:
        raise ValueError("tenant_id cannot be empty")
    if len(tenant_id) > 64:
        raise ValueError("tenant_id exceeds maximum length of 64 characters")
    if "\x00" in tenant_id:
        raise ValueError("tenant_id contains null bytes")
    if not re.match(r"^[a-zA-Z0-9_-]+$", tenant_id):
        raise ValueError("tenant_id contains invalid characters (only alphanumeric, dash, underscore allowed)")
    return tenant_id


def sanitize_message(message: str) -> str:
    """Sanitize message content by stripping control characters and limiting length.

    Args:
        message: The message to sanitize.

    Returns:
        Sanitized message string.
    """
    # Strip control characters except newline and tab
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", message)
    # Limit length to 10000 characters
    return sanitized[:10000]
