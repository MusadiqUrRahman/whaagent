"""Tests for scheduler functions."""

from datetime import UTC, datetime

import pytest

from whaagent.storage.scheduler import calculate_next_run, parse_natural_time


def test_parse_natural_time_specific() -> None:
    """Test parsing specific time expressions."""
    result, cron = parse_natural_time("tomorrow at 9am")
    assert isinstance(result, datetime)
    assert cron is None


def test_parse_natural_time_duration() -> None:
    """Test parsing duration-based time expressions."""
    result, cron = parse_natural_time("in 2 hours")
    assert isinstance(result, datetime)
    assert cron is None


def test_parse_natural_time_daily() -> None:
    """Test parsing daily recurring expressions."""
    result, cron = parse_natural_time("daily at 9am")
    assert isinstance(result, datetime)
    assert cron is not None
    assert "0" in cron  # minute
    assert "9" in cron  # hour


def test_parse_natural_time_every_minute() -> None:
    """Test parsing 'every minute' recurring expression."""
    result, cron = parse_natural_time("every minute")
    assert isinstance(result, datetime)
    assert cron == "* * * * *"


def test_parse_natural_time_invalid() -> None:
    """Test parsing invalid time expressions."""
    with pytest.raises(ValueError):
        parse_natural_time("not a time")


def test_calculate_next_run() -> None:
    """Test calculating next run from cron expression."""
    now = datetime.now(UTC)
    result = calculate_next_run("0 * * * *")
    assert isinstance(result, datetime)
    assert result > now


def test_calculate_next_run_invalid() -> None:
    """Test calculating next run with invalid cron expression."""
    with pytest.raises(ValueError):
        calculate_next_run("invalid cron")


def test_parse_natural_time_weekly() -> None:
    """Test parsing weekly recurring expressions."""
    result, cron = parse_natural_time("weekly on monday")
    assert isinstance(result, datetime)
    assert cron is not None
    assert "0" in cron  # minute
    assert "0" in cron  # hour


def test_parse_natural_time_monthly() -> None:
    """Test parsing monthly recurring expressions."""
    result, cron = parse_natural_time("monthly on day 15")
    assert isinstance(result, datetime)
    assert cron is not None
    assert "15" in cron
