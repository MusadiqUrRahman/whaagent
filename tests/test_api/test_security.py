"""Tests for security module."""

import time

import pytest

from whaagent.api.security import RateLimiter, sanitize_message, validate_tenant_id


class TestRateLimiter:
    """Test the RateLimiter class."""

    def test_allows_under_threshold(self):
        """Test that requests under the threshold are allowed."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed("tenant-1") is True
        assert limiter.is_allowed("tenant-1") is True
        assert limiter.is_allowed("tenant-1") is True

    def test_blocks_over_threshold(self):
        """Test that requests over the threshold are blocked."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("tenant-1")
        limiter.is_allowed("tenant-1")
        assert limiter.is_allowed("tenant-1") is False

    def test_separate_tenants_tracked_independently(self):
        """Test that different tenants are tracked separately."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed("tenant-1")
        assert limiter.is_allowed("tenant-1") is False
        assert limiter.is_allowed("tenant-2") is True

    def test_window_cleanup_removes_old_requests(self):
        """Test that old requests are cleaned from the window."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)

        # Make two requests to fill the quota
        limiter.is_allowed("tenant-1")
        limiter.is_allowed("tenant-1")
        assert limiter.is_allowed("tenant-1") is False

        # Wait for the window to expire
        time.sleep(1.1)

        # Now should be allowed again since the window has passed
        assert limiter.is_allowed("tenant-1") is True

    def test_custom_window_and_limits(self):
        """Test with custom max requests and window size."""
        limiter = RateLimiter(max_requests=5, window_seconds=30)
        for _ in range(5):
            assert limiter.is_allowed("tenant-1") is True
        assert limiter.is_allowed("tenant-1") is False


class TestValidateTenantId:
    """Test tenant ID validation."""

    def test_valid_ids(self):
        """Test that valid tenant IDs are accepted."""
        assert validate_tenant_id("personal") == "personal"
        assert validate_tenant_id("my-tenant_1") == "my-tenant_1"
        assert validate_tenant_id("tenant-123_abc") == "tenant-123_abc"
        assert validate_tenant_id("A") == "A"
        assert validate_tenant_id("a" * 64) == "a" * 64  # Maximum length

    def test_rejects_path_traversal(self):
        """Test that path traversal attempts are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_tenant_id("../../../etc/passwd")
        with pytest.raises(ValueError, match="invalid characters"):
            validate_tenant_id("../tenant")
        with pytest.raises(ValueError, match="invalid characters"):
            validate_tenant_id("tenant/../../../etc")

    def test_rejects_null_bytes(self):
        """Test that null bytes are rejected."""
        with pytest.raises(ValueError, match="null bytes"):
            validate_tenant_id("tenant\x00admin")
        with pytest.raises(ValueError, match="null bytes"):
            validate_tenant_id("tenant\x00")

    def test_rejects_empty(self):
        """Test that empty tenant IDs are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_tenant_id("")

    def test_rejects_too_long(self):
        """Test that tenant IDs longer than 64 characters are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_tenant_id("a" * 65)

    def test_rejects_invalid_characters(self):
        """Test that tenant IDs with invalid characters are rejected."""
        invalid_chars = [
            " ",
            "@",
            "#",
            "$",
            "%",
            "^",
            "&",
            "*",
            "(",
            ")",
            "+",
            "=",
            "[",
            "]",
            "{",
            "}",
            "|",
            "\\",
            ":",
            ";",
            '"',
            "'",
            "<",
            ">",
            ",",
            "?",
            "/",
            "~",
            "`",
        ]
        for char in invalid_chars:
            with pytest.raises(ValueError, match="invalid characters"):
                validate_tenant_id(f"tenant{char}admin")

    def test_rejects_unicode(self):
        """Test that Unicode characters are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_tenant_id("tenant-中文")
        with pytest.raises(ValueError, match="invalid characters"):
            validate_tenant_id("tenant-ñ")


class TestSanitizeMessage:
    """Test message sanitization."""

    def test_strips_control_chars(self):
        """Test that control characters are stripped."""
        assert sanitize_message("hello\x00world") == "helloworld"
        assert sanitize_message("hello\x01world") == "helloworld"
        assert sanitize_message("hello\x08world") == "helloworld"
        assert sanitize_message("hello\x0bworld") == "helloworld"
        assert sanitize_message("hello\x0cworld") == "helloworld"
        assert sanitize_message("hello\x1eworld") == "helloworld"
        assert sanitize_message("hello\x7fworld") == "helloworld"

    def test_preserves_newlines_and_tabs(self):
        """Test that newlines and tabs are preserved."""
        assert sanitize_message("hello\nworld") == "hello\nworld"
        assert sanitize_message("hello\tworld") == "hello\tworld"
        assert sanitize_message("line1\nline2\nline3") == "line1\nline2\nline3"

    def test_limits_length(self):
        """Test that message length is limited."""
        long_msg = "a" * 20000
        result = sanitize_message(long_msg)
        assert len(result) == 10000
        assert result == "a" * 10000

    def test_handles_empty_string(self):
        """Test that empty strings are handled correctly."""
        assert sanitize_message("") == ""

    def test_normal_strings_unchanged(self):
        """Test that normal strings are unchanged (within length limit)."""
        normal_msg = "Hello, world! This is a normal message."
        assert sanitize_message(normal_msg) == normal_msg

    def test_short_string_within_limit(self):
        """Test that short strings are not truncated."""
        short_msg = "short message"
        assert sanitize_message(short_msg) == short_msg

    def test_whitespace_preserved(self):
        """Test that whitespace is preserved."""
        msg = "  Hello   world  \n\t  "
        assert sanitize_message(msg) == "  Hello   world  \n\t  "
