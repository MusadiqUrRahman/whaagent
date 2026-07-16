"""Time parsing and scheduling utilities."""

import logging
import re
from datetime import datetime

import croniter
import dateparser

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for recurring time expressions (efficiency: compile once at module load)
RECURRING_PATTERNS = [
    (
        re.compile(
            r"every\s+(second|seconds|minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)",
            re.IGNORECASE,
        ),
        "simple",
    ),
    (
        re.compile(
            r"daily\s+at\s+(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm))?|daily|everyday",
            re.IGNORECASE,
        ),
        "daily",
    ),
    (
        re.compile(
            r"weekly\s+on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)|weekly",
            re.IGNORECASE,
        ),
        "weekly",
    ),
    (
        re.compile(r"monthly\s+on\s+day\s+(\d{1,2})|monthly", re.IGNORECASE),
        "monthly",
    ),
]


def parse_natural_time(time_str: str) -> tuple[datetime, str | None]:
    """Parse natural language time expression.

    Args:
        time_str: Natural language time string (e.g., "tomorrow at 8am", "in 2 hours").

    Returns:
        Tuple of (parsed datetime, cron_expression or None).

    Raises:
        ValueError: If time string cannot be parsed.
    """
    # Check for recurring patterns first
    cron_expr = None
    for pattern, pattern_type in RECURRING_PATTERNS:
        match = pattern.search(time_str)
        if match:
            cron_expr = _pattern_to_cron(match, pattern_type)
            if cron_expr:
                next_run = calculate_next_run(cron_expr)
                logger.debug(f"Parsed recurring time: {time_str} -> {cron_expr}")
                return next_run, cron_expr

    # Parse one-time time using dateparser
    parsed = dateparser.parse(time_str)
    if parsed is None:
        raise ValueError(f"Could not parse time expression: {time_str}")

    # Ensure timezone-naive for compatibility
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)

    logger.debug(f"Parsed time: {time_str} -> {parsed}")
    return parsed, None


def _pattern_to_cron(match: re.Match, pattern_type: str) -> str | None:
    """Convert regex match to cron expression.

    Args:
        match: Regex match object.
        pattern_type: Type of pattern matched.

    Returns:
        Cron expression string or None if conversion failed.
    """
    if pattern_type == "simple":
        unit = match.group(1).lower()
        # "every minute" -> "* * * * *"
        if unit in ("minute", "minutes"):
            return "* * * * *"
        elif unit in ("hour", "hours"):
            return "0 * * * *"
        elif unit in ("day", "days"):
            return "0 0 * * *"
        elif unit in ("week", "weeks"):
            return "0 0 * * 0"
        elif unit in ("month", "months"):
            return "0 0 1 * *"
        elif unit in ("year", "years"):
            return "0 0 1 1 *"
    elif pattern_type == "daily":
        hour = match.group(1) or "0"
        minute = match.group(2) or "0"
        ampm = match.group(3) or "am"
        h = int(hour)
        m = int(minute)
        if ampm.lower() == "pm" and h != 12:
            h += 12
        elif ampm.lower() == "am" and h == 12:
            h = 0
        return f"{m} {h} * * *"
    elif pattern_type == "weekly":
        day_map = {
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
            "sunday": 0,
        }
        day = (match.group(1) or "monday").lower()
        return f"0 0 * * {day_map[day]}"
    elif pattern_type == "monthly":
        day = int(match.group(1) or "1")
        return f"0 0 {day} * *"
    return None


def calculate_next_run(cron_expression: str) -> datetime:
    """Calculate next execution time from cron expression.

    Args:
        cron_expression: Cron expression (5 fields: minute hour day month weekday).

    Returns:
        Next execution datetime.

    Raises:
        ValueError: If cron expression is invalid.
    """
    try:
        from datetime import UTC

        cron = croniter.croniter(cron_expression, datetime.now(UTC))
        next_run = cron.get_next(datetime)
        logger.debug(f"Calculated next run for {cron_expression}: {next_run}")
        return next_run
    except ValueError as e:
        raise ValueError(f"Invalid cron expression: {cron_expression}") from e
