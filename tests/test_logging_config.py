"""Tests for structured logging configuration with PII sanitization."""

import logging
import re
from unittest.mock import Mock, patch

from whaagent.config import whaagentConfig, LoggingConfig
from whaagent.logging_config import PIIFilter, TenantLogAdapter, setup_logging


class TestPIIFilter:
    """Test cases for PIIFilter class."""

    def test_phone_number_sanitization(self):
        """Test that phone numbers are properly sanitized."""
        piifilter = PIIFilter()

        # Test various phone number formats
        test_cases = [
            ("Call me at +1234567890", "Call me at [REDACTED_PHONE]"),
            ("My number is +15551234567", "My number is [REDACTED_PHONE]"),
            ("WhatsApp: +447700900123", "WhatsApp: [REDACTED_PHONE]"),
            ("No phone here", "No phone here"),  # No change
        ]

        for input_text, expected in test_cases:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0, msg=input_text, args=(), exc_info=None
            )

            assert piifilter.filter(record) is True
            assert record.msg == expected

    def test_api_key_sanitization(self):
        """Test that API keys are properly sanitized."""
        piifilter = PIIFilter()

        test_cases = [
            ("My api_key=abc123def456", "My [REDACTED_KEY]"),
            ("API_KEY = secret789key", "[REDACTED_KEY]"),
            ("token is xyz-api-key-12345678", "token is xyz-api-key-12345678"),  # No match (no space before key)
            ("Normal text", "Normal text"),  # No change
        ]

        for input_text, expected in test_cases:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0, msg=input_text, args=(), exc_info=None
            )

            assert piifilter.filter(record) is True
            assert record.msg == expected

    def test_message_content_sanitization(self):
        """Test that long message content is sanitized."""
        piifilter = PIIFilter()

        test_cases = [
            (
                "user said message='Hello this is a very long message that should be redacted'",
                "user said message[REDACTED_MESSAGE]",
            ),
            ('message="Short message"', 'message="Short message"'),  # Too short
            ("No message here", "No message here"),  # No match
        ]

        for input_text, expected in test_cases:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0, msg=input_text, args=(), exc_info=None
            )

            assert piifilter.filter(record) is True
            assert record.msg == expected

    def test_below_info_level_no_sanitization(self):
        """Test that messages below INFO level are not sanitized."""
        piifilter = PIIFilter()

        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,  # Below INFO
            pathname="",
            lineno=0,
            msg="API key: secret123",
            args=(),
            exc_info=None,
        )

        assert piifilter.filter(record) is True
        assert record.msg == "API key: secret123"  # Not sanitized

    def test_args_sanitization(self):
        """Test that format arguments are also sanitized."""
        piifilter = PIIFilter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="User %s called from %s",
            args=("John", "+1234567890"),
            exc_info=None,
        )

        assert piifilter.filter(record) is True
        assert record.msg == "User %s called from %s"
        assert record.args == ("John", "[REDACTED_PHONE]")

    def test_regex_patterns_compiled(self):
        """Test that regex patterns are compiled correctly."""
        assert isinstance(PIIFilter.PHONE_PATTERN, re.Pattern)
        assert isinstance(PIIFilter.API_KEY_PATTERN, re.Pattern)
        assert isinstance(PIIFilter.MESSAGE_CONTENT_PATTERN, re.Pattern)


class TestTenantLogAdapter:
    """Test cases for TenantLogAdapter class."""

    def test_process_adds_tenant_id(self):
        """Test that tenant_id is added to log messages."""
        mock_logger = Mock()
        adapter = TenantLogAdapter(mock_logger, "tenant-123")

        msg, kwargs = adapter.process("Hello world", {"extra": "data"})

        assert msg == "[tenant-123] Hello world"
        assert kwargs == {"extra": "data"}

    def test_get_logger_with_tenant(self):
        """Test getting a logger with tenant context."""
        mock_logger = Mock()
        adapter = TenantLogAdapter(mock_logger, "original-tenant")

        new_logger = adapter.get_logger("new-tenant")
        assert isinstance(new_logger, TenantLogAdapter)
        assert new_logger.tenant_id == "new-tenant"
        assert new_logger.logger is mock_logger

    def test_get_logger_without_tenant(self):
        """Test getting the original logger without tenant context."""
        mock_logger = Mock()
        adapter = TenantLogAdapter(mock_logger, "tenant-123")

        original_logger = adapter.get_logger()
        assert original_logger is mock_logger


class TestSetupLogging:
    """Test cases for setup_logging function."""

    def test_setup_logging_with_file_config(self):
        """Test setup logging with file configuration."""
        with patch("whaagent.logging_config.logging") as mock_logging:
            with patch("whaagent.logging_config.Path") as mock_path:
                mock_path.return_value.exists.return_value = False
                mock_path.return_value.mkdir.return_value = None
                mock_path.return_value.joinpath.return_value = Mock()
                mock_path.return_value.joinpath.return_value.__enter__ = Mock()
                mock_path.return_value.joinpath.return_value.__exit__ = Mock()
                mock_path.return_value.joinpath.return_value.__str__ = Mock(return_value="mock_path")

                mock_logger = Mock()
                mock_logging.getLogger.return_value = mock_logger
                mock_handler = Mock()
                mock_logging.FileHandler.return_value = mock_handler

                config = whaagentConfig()
                config.logging = LoggingConfig(level="DEBUG", file="logs/api.log", directory="logs")

                setup_logging(config)

                # Check that FileHandler was created
                mock_logging.FileHandler.assert_called()
                # Check that handler was added to logger
                mock_logger.addHandler.assert_called()

    def test_setup_logging_with_directory_only(self):
        """Test setup logging with directory configuration only."""
        with patch("whaagent.logging_config.logging") as mock_logging:
            with patch("whaagent.logging_config.Path") as mock_path:
                mock_path.return_value.exists.return_value = False
                mock_path.return_value.mkdir.return_value = None
                mock_path.return_value.joinpath.return_value = Mock()
                mock_path.return_value.joinpath.return_value.__enter__ = Mock()
                mock_path.return_value.joinpath.return_value.__exit__ = Mock()
                mock_path.return_value.joinpath.return_value.__str__ = Mock(return_value="mock_path")

                mock_logger = Mock()
                mock_logging.getLogger.return_value = mock_logger
                mock_handler = Mock()
                mock_logging.FileHandler.return_value = mock_handler

                config = whaagentConfig()
                config.logging = LoggingConfig(level="INFO", directory="logs")

                setup_logging(config)

                # Check that FileHandler was created
                mock_logging.FileHandler.assert_called()
                # Check that handler was added to logger
                mock_logger.addHandler.assert_called()

    def test_setup_logging_with_default_directory(self):
        """Test setup logging with default directory."""
        with patch("whaagent.logging_config.logging") as mock_logging:
            with patch("whaagent.logging_config.Path") as mock_path:
                mock_path.return_value.exists.return_value = False
                mock_path.return_value.mkdir.return_value = None
                mock_path.return_value.joinpath.return_value = Mock()
                mock_path.return_value.joinpath.return_value.__enter__ = Mock()
                mock_path.return_value.joinpath.return_value.__exit__ = Mock()
                mock_path.return_value.joinpath.return_value.__str__ = Mock(return_value="mock_path")

                mock_logger = Mock()
                mock_logging.getLogger.return_value = mock_logger
                mock_handler = Mock()
                mock_logging.FileHandler.return_value = mock_handler

                config = whaagentConfig()
                config.logging = LoggingConfig(level="WARNING", file=None, directory=None)

                setup_logging(config)

                # Check that FileHandler was created
                mock_logging.FileHandler.assert_called()
                # Check that handler was added to logger
                mock_logger.addHandler.assert_called()

    @patch("whaagent.logging_config.logging")
    def test_log_level_conversion(self, mock_logging):
        """Test that log level strings are converted correctly."""
        mock_get_logger = Mock()
        mock_get_logger.return_value = Mock()
        mock_logging.getLogger = mock_get_logger
        mock_logging.ERROR = 40  # Mock the logging.ERROR constant

        config = whaagentConfig()
        config.logging = LoggingConfig(level="ERROR", file=None, directory=None)

        setup_logging(config)

        # Check that root logger was configured with ERROR level
        mock_get_logger.return_value.setLevel.assert_called_with(40)  # ERROR level

    def test_setup_logging_creates_handlers(self):
        """Test that setup logging creates appropriate handlers."""
        with patch("whaagent.logging_config.logging") as mock_logging:
            with patch("whaagent.logging_config.Path") as mock_path:
                mock_path.return_value.parent = mock_path.return_value
                mock_path.return_value.__truediv__ = lambda self, other: mock_path.return_value
                mock_path.return_value.exists.return_value = False
                mock_path.return_value.mkdir.return_value = None

                mock_path.return_value.joinpath.return_value.__enter__ = Mock()
                mock_path.return_value.joinpath.return_value.__exit__ = Mock()

                config = whaagentConfig()
                config.logging = LoggingConfig(level="INFO", file="logs/api.log", directory="logs")

                setup_logging(config)

                # Check that handlers were added
                assert mock_logging.getLogger.return_value.addHandler.call_count >= 1

    @patch("whaagent.logging_config.logging")
    def test_setup_logging_info_message(self, mock_logging):
        """Test that setup completion is logged."""
        mock_logger = Mock()
        mock_logging.getLogger.return_value = mock_logger

        with patch("whaagent.logging_config.Path") as mock_path:
            mock_path.return_value.parent = mock_path.return_value
            mock_path.return_value.__truediv__ = lambda self, other: mock_path.return_value
            mock_path.return_value.exists.return_value = False
            mock_path.return_value.mkdir.return_value = None
            mock_path.return_value.joinpath.return_value.__enter__ = Mock()
            mock_path.return_value.joinpath.return_value.__exit__ = Mock()

            config = whaagentConfig()
            config.logging = LoggingConfig(level="INFO", file="logs/api.log", directory="logs")

            setup_logging(config)

            # Check that setup completion was logged
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "Logging configured" in call_args
            assert "api.log" in call_args
            assert "whatsapp.log" in call_args


class TestIntegration:
    """Integration tests for the logging configuration."""

    def test_combined_pii_sanitization(self):
        """Test that multiple PII elements are sanitized together."""
        piifilter = PIIFilter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="User %s called from %s with message='Hello this is a very long message that should be redacted'",
            args=("John", "+1234567890"),
            exc_info=None,
        )

        piifilter.filter(record)

        assert "John" in record.args[0]  # Name not sanitized
        assert record.args[1] == "[REDACTED_PHONE]"  # Phone sanitized
        assert "message[REDACTED_MESSAGE]" in record.msg  # Message content sanitized

    def test_tenant_adapter_with_filter_integration(self):
        """Test that tenant adapter works with PII filter."""
        mock_logger = Mock()
        adapter = TenantLogAdapter(mock_logger, "tenant-456")

        # Create a record with PII
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Message from +1234567890: Hello world",
            args=(),
            exc_info=None,
        )

        # Apply PII filter
        piifilter = PIIFilter()
        piifilter.filter(record)

        # Process with tenant adapter
        msg, kwargs = adapter.process(record.msg, {})

        assert msg == "[tenant-456] Message from [REDACTED_PHONE]: Hello world"
        assert kwargs == {}
