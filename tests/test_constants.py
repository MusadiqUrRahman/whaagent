"""Tests for whaagent constants."""

from pathlib import Path


def test_storage_dir_is_absolute_path():
    """STORAGE_DIR should be an absolute Path."""
    from whaagent.constants import STORAGE_DIR

    assert isinstance(STORAGE_DIR, Path)
    assert STORAGE_DIR.is_absolute()


def test_logs_dir_is_absolute_path():
    """LOGS_DIR should be an absolute Path."""
    from whaagent.constants import LOGS_DIR

    assert isinstance(LOGS_DIR, Path)
    assert LOGS_DIR.is_absolute()


def test_storage_dir_contains_app_name():
    """STORAGE_DIR should contain the app name."""
    from whaagent.constants import STORAGE_DIR

    assert "whaagent" in str(STORAGE_DIR)


def test_logs_dir_contains_app_name():
    """LOGS_DIR should contain the app name."""
    from whaagent.constants import LOGS_DIR

    assert "whaagent" in str(LOGS_DIR)
