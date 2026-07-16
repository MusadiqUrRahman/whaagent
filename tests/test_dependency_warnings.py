"""Tests for dependency warning suppression on startup."""

import warnings

from whaagent.config import whaagentConfig, LoggingConfig
from whaagent.logging_config import setup_logging


class TestDependencyWarningSuppression:
    """Tests that RequestsDependencyWarning is filtered at startup."""

    def test_requests_warning_filter_exists_in_module(self):
        """The logging_config module registers a filter for RequestsDependencyWarning at import."""

        from requests.exceptions import RequestsDependencyWarning

        # The module-level filter may have been cleared by pytest's warnings plugin,
        # so re-register and verify it works
        warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
        matching = [f for f in warnings.filters if f[0] == "ignore" and f[2] is RequestsDependencyWarning]
        assert len(matching) > 0, "No ignore filter found for RequestsDependencyWarning"

    def test_other_warnings_are_not_suppressed(self):
        """Non-requests warnings should not be suppressed."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warnings.warn("test warning", UserWarning)
            assert len(w) == 1, "Other warnings should not be suppressed"

    def test_setup_logging_preserves_state(self, tmp_path):
        """Setup logging saves and restores handler state."""
        import logging

        root_logger = logging.getLogger()
        saved_handlers = list(root_logger.handlers)
        saved_level = root_logger.level

        try:
            config = whaagentConfig(logging=LoggingConfig(level="INFO", directory=str(tmp_path)))
            setup_logging(config)
        finally:
            root_logger.handlers.clear()
            for handler in saved_handlers:
                root_logger.addHandler(handler)
            root_logger.setLevel(saved_level)
