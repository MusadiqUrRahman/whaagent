"""Structured logging configuration with PII sanitization for whaagent."""

import logging
import re
import warnings
from pathlib import Path
from typing import Any

from whaagent.config import whaagentConfig

# Suppress requests library dependency version mismatch warnings at import time.
# This must happen before any code imports requests transitively.
try:
    from requests import RequestsDependencyWarning  # type: ignore[attr-defined]

    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except ImportError:
    pass


class PIIFilter(logging.Filter):
    """Redacts PII from log records at INFO level and above."""

    # Patterns to redact
    PHONE_PATTERN = re.compile(r"\+\d{10,15}")
    API_KEY_PATTERN = re.compile(r'(api[_-]?key\s*[=:]\s*["\']?[\w-]{8,}["\']?)', re.IGNORECASE)
    MESSAGE_CONTENT_PATTERN = re.compile(r'message[\s:=]+["\'][^"\']{50,}["\']', re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and sanitize log record if at INFO level or above."""
        if record.levelno >= logging.INFO and record.msg:
            record.msg = self._sanitize(str(record.msg))
            if record.args:
                record.args = tuple(self._sanitize(str(a)) for a in record.args)
        return True

    def _sanitize(self, text: str) -> str:
        """Sanitize text by removing PII."""
        # Redact phone numbers
        text = self.PHONE_PATTERN.sub("[REDACTED_PHONE]", text)

        # Redact API keys
        text = self.API_KEY_PATTERN.sub("[REDACTED_KEY]", text)

        # Redact long message content (likely WhatsApp messages)
        text = self.MESSAGE_CONTENT_PATTERN.sub("message[REDACTED_MESSAGE]", text)

        return text


class ThirdPartyLogFilter(logging.Filter):
    """Suppresses logging format errors from third-party libraries.

    Handles known format mismatches:
    - openai._base_client: uses %f with string timeout arg on retry logs
    - httpx: uses %d with string status code arg
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out malformed log records from third-party libraries."""
        if not record.args or not isinstance(record.msg, str):
            return True
        try:
            # Test if the format string works with the provided args
            record.msg % record.args
            return True
        except (TypeError, ValueError):
            # Format mismatch — suppress this log record to avoid
            # "Logging error" tracebacks from third-party libraries.
            return False


class TenantLogAdapter(logging.LoggerAdapter):
    """Adds tenant_id to log entries."""

    def __init__(self, logger: logging.Logger, tenant_id: str):
        """Initialize adapter with logger and tenant_id."""
        super().__init__(logger, {})
        self.tenant_id = tenant_id

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """Add tenant_id to log message."""
        return f"[{self.tenant_id}] {msg}", kwargs

    def get_logger(self, tenant_id: str | None = None) -> Any:
        """Get a logger instance with tenant context."""
        if tenant_id:
            return TenantLogAdapter(self.logger, tenant_id)
        return self.logger


def setup_logging(config: whaagentConfig) -> None:
    """Configure structured logging with PII sanitization.

    Args:
        config: The whaagent configuration instance.
    """
    # Convert string log level to logging constant
    try:
        level = getattr(logging, config.logging.level.upper())
    except (AttributeError, ValueError):
        level = logging.INFO

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler with PII filter and httpx error suppression
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(PIIFilter())
    console_handler.addFilter(ThirdPartyLogFilter())
    root_logger.addHandler(console_handler)

    # Determine log directory
    log_file = config.logging.file
    if log_file:
        log_dir = Path(log_file).parent
    else:
        # Use directory config if available, otherwise default to logs/
        log_dir = Path(config.logging.directory) if config.logging.directory else Path("logs")

    log_dir.mkdir(parents=True, exist_ok=True)

    # API log handler
    api_log_file = log_dir / "api.log"
    api_handler = logging.FileHandler(api_log_file)
    api_handler.setFormatter(formatter)
    api_handler.addFilter(PIIFilter())

    # Create logger for API routes and add handler
    api_logger = logging.getLogger("whaagent.api")
    api_logger.addHandler(api_handler)
    api_logger.setLevel(level)

    # WhatsApp log handler
    wa_log_file = log_dir / "whatsapp.log"
    wa_handler = logging.FileHandler(wa_log_file)
    wa_handler.setFormatter(formatter)
    wa_handler.addFilter(PIIFilter())

    # Create logger for WhatsApp routes and add handler
    wa_logger = logging.getLogger("whaagent.api.routes.whatsapp")
    wa_logger.addHandler(wa_handler)
    wa_logger.setLevel(level)

    # Log setup completion
    setup_logger = logging.getLogger(__name__)
    setup_logger.info(
        "Logging configured - level: %s, api.log: %s, whatsapp.log: %s", config.logging.level, api_log_file, wa_log_file
    )
