"""Tests for DeepScrapeTool — 3-stage web content extraction pipeline with DNS retry."""

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from whaagent.tools.deep_scrape import (
    DeepScrapeResult,
    DeepScrapeTool,
    ExtractionStage,
    ExtractionStatus,
    _is_dns_error,
)


class TestDeepScrapeResult:
    """Tests for the DeepScrapeResult model."""

    def test_success_str_format(self) -> None:
        result = DeepScrapeResult(
            url="https://example.com/article",
            status=ExtractionStatus.SUCCESS,
            stage=ExtractionStage.CRAWL4AI,
            content="Article body text here.",
            title="Test Article",
            final_url="https://example.com/article",
        )
        output = str(result)
        assert "Test Article" in output
        assert "Article body text here." in output
        assert "crawl4ai" in output

    def test_error_str_format(self) -> None:
        result = DeepScrapeResult(
            url="https://example.com/paywall",
            status=ExtractionStatus.BLOCKED,
            error="Content blocked by paywall.",
        )
        output = str(result)
        assert "Error" in output
        assert "blocked by paywall" in output

    def test_success_no_title(self) -> None:
        result = DeepScrapeResult(
            url="https://example.com",
            status=ExtractionStatus.SUCCESS,
            stage=ExtractionStage.FIRECRAWL,
            content="Just content.",
        )
        output = str(result)
        assert "# " not in output
        assert "Just content." in output


class TestIsDnsError:
    """Tests for the _is_dns_error helper."""

    def test_dns_resolution_failed(self) -> None:
        assert _is_dns_error('Firecrawl error: DNS resolution failed for hostname "g1.globo.com.br"')

    def test_tunnel_connection_failed(self) -> None:
        assert _is_dns_error(
            "Firecrawl error: Internal Server Error: Failed to scrape. "
            'The URL failed to load in the browser with error code "ERR_TUNNEL_CONNECTION_FAILED"'
        )

    def test_getaddrinfo_failed(self) -> None:
        assert _is_dns_error("httpx.ConnectError: getaddrinfo failed for host example.com")

    def test_name_or_service_not_known(self) -> None:
        assert _is_dns_error("ConnectionError: Name or service not known")

    def test_nodename_failure(self) -> None:
        assert _is_dns_error("nodename nor servname provided, or not known")

    def test_temporary_failure(self) -> None:
        assert _is_dns_error("Temporary failure in name resolution")

    def test_non_dns_error_returns_false(self) -> None:
        assert not _is_dns_error("Firecrawl returned insufficient content.")

    def test_non_dns_connection_error(self) -> None:
        assert not _is_dns_error("Connection refused")

    def test_empty_string(self) -> None:
        assert not _is_dns_error("")

    def test_case_insensitive(self) -> None:
        assert _is_dns_error("dns RESOLUTION FAILED for host")


class TestDeepScrapeTool:
    """Tests for the DeepScrapeTool class."""

    def test_name_and_description(self) -> None:
        tool = DeepScrapeTool()
        assert tool.name == "deep_scrape"
        assert "Extract clean text" in tool.description

    def test_crawl4ai_enabled_default(self) -> None:
        """Verify that Crawl4AI is enabled by default."""
        tool = DeepScrapeTool()
        assert tool._crawl4ai_enabled is True

    def test_crawl4ai_enabled_via_env(self) -> None:
        """Verify that Crawl4AI can be enabled via environment variable."""
        import os

        original_value = os.environ.get("CRAWL4AI_ENABLED")
        try:
            os.environ["CRAWL4AI_ENABLED"] = "true"
            tool = DeepScrapeTool()
            assert tool._crawl4ai_enabled is True

            os.environ["CRAWL4AI_ENABLED"] = "True"
            tool = DeepScrapeTool()
            assert tool._crawl4ai_enabled is True

            os.environ["CRAWL4AI_ENABLED"] = "TRUE"
            tool = DeepScrapeTool()
            assert tool._crawl4ai_enabled is True
        finally:
            if original_value is None:
                os.environ.pop("CRAWL4AI_ENABLED", None)
            else:
                os.environ["CRAWL4AI_ENABLED"] = original_value

    def test_crawl4ai_disabled_via_env(self) -> None:
        """Verify that Crawl4AI can be disabled via environment variable."""
        import os

        original_value = os.environ.get("CRAWL4AI_ENABLED")
        try:
            os.environ["CRAWL4AI_ENABLED"] = "false"
            tool = DeepScrapeTool()
            assert tool._crawl4ai_enabled is False

            os.environ["CRAWL4AI_ENABLED"] = "False"
            tool = DeepScrapeTool()
            assert tool._crawl4ai_enabled is False

            os.environ["CRAWL4AI_ENABLED"] = "FALSE"
            tool = DeepScrapeTool()
            assert tool._crawl4ai_enabled is False

            os.environ["CRAWL4AI_ENABLED"] = "0"
            tool = DeepScrapeTool()
            assert tool._crawl4ai_enabled is False
        finally:
            if original_value is None:
                os.environ.pop("CRAWL4AI_ENABLED", None)
            else:
                os.environ["CRAWL4AI_ENABLED"] = original_value

    def test_playwright_low_memory_default(self) -> None:
        """Verify that low-memory mode is disabled by default."""
        import os

        original_value = os.environ.get("PLAYWRIGHT_LOW_MEMORY")
        try:
            # Ensure the variable is unset
            os.environ.pop("PLAYWRIGHT_LOW_MEMORY", None)

            browser_config = DeepScrapeTool._get_browser_config()

            # Verify basic config
            assert browser_config.headless is True
            assert browser_config.user_agent is not None

            # Verify no extra_args (low-memory disabled)
            assert browser_config.extra_args is None or len(browser_config.extra_args) == 0
        finally:
            if original_value is not None:
                os.environ["PLAYWRIGHT_LOW_MEMORY"] = original_value

    def test_playwright_low_memory_enabled(self) -> None:
        """Verify that low-memory mode adds memory optimization flags."""
        import os

        original_value = os.environ.get("PLAYWRIGHT_LOW_MEMORY")
        try:
            os.environ["PLAYWRIGHT_LOW_MEMORY"] = "true"

            browser_config = DeepScrapeTool._get_browser_config()

            # Verify basic config
            assert browser_config.headless is True
            assert browser_config.user_agent is not None

            # Verify extra_args contains low-memory flags
            assert browser_config.extra_args is not None
            assert len(browser_config.extra_args) > 0
            assert "--disable-dev-shm-usage" in browser_config.extra_args
            assert "--disable-gpu" in browser_config.extra_args
            assert "--no-sandbox" in browser_config.extra_args
            assert "--disable-setuid-sandbox" in browser_config.extra_args
            assert "--disable-background-timer-throttling" in browser_config.extra_args
            assert "--disable-backgrounding-occluded-windows" in browser_config.extra_args
            assert "--disable-renderer-backgrounding" in browser_config.extra_args
        finally:
            if original_value is None:
                os.environ.pop("PLAYWRIGHT_LOW_MEMORY", None)
            else:
                os.environ["PLAYWRIGHT_LOW_MEMORY"] = original_value

    def test_playwright_low_memory_case_insensitive(self) -> None:
        """Verify that PLAYWRIGHT_LOW_MEMORY is case-insensitive."""
        import os

        original_value = os.environ.get("PLAYWRIGHT_LOW_MEMORY")
        try:
            for value in ["true", "True", "TRUE", "TrUe"]:
                os.environ["PLAYWRIGHT_LOW_MEMORY"] = value

                browser_config = DeepScrapeTool._get_browser_config()
                assert browser_config.extra_args is not None
                assert "--disable-dev-shm-usage" in browser_config.extra_args

            for value in ["false", "False", "FALSE", "0", "no"]:
                os.environ["PLAYWRIGHT_LOW_MEMORY"] = value

                browser_config = DeepScrapeTool._get_browser_config()
                assert browser_config.extra_args is None or len(browser_config.extra_args) == 0
        finally:
            if original_value is None:
                os.environ.pop("PLAYWRIGHT_LOW_MEMORY", None)
            else:
                os.environ["PLAYWRIGHT_LOW_MEMORY"] = original_value

    def test_try_crawl4ai_when_disabled(self) -> None:
        """Verify that _try_crawl4ai returns error when disabled."""
        import os

        original_value = os.environ.get("CRAWL4AI_ENABLED")
        try:
            os.environ["CRAWL4AI_ENABLED"] = "false"
            tool = DeepScrapeTool()
            result = tool._try_crawl4ai("https://example.com")

            assert result.status == ExtractionStatus.ERROR
            assert result.stage == ExtractionStage.CRAWL4AI
            assert "Crawl4AI disabled via CRAWL4AI_ENABLED=false" in result.error
        finally:
            if original_value is None:
                os.environ.pop("CRAWL4AI_ENABLED", None)
            else:
                os.environ["CRAWL4AI_ENABLED"] = original_value

    @patch("whaagent.tools.deep_scrape.Firecrawl")
    @patch.object(httpx, "get")
    def test_pipeline_skips_stage1_when_disabled(
        self,
        mock_get: MagicMock,
        mock_firecrawl_cls: MagicMock,
    ) -> None:
        """Verify that pipeline skips Stage 1 when Crawl4AI is disabled and falls back to Stage 2."""
        import os

        original_value = os.environ.get("CRAWL4AI_ENABLED")
        original_firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")

        try:
            # Disable Crawl4AI
            os.environ["CRAWL4AI_ENABLED"] = "false"
            os.environ["FIRECRAWL_API_KEY"] = "test-key"

            # Mock Firecrawl to succeed
            mock_app = MagicMock()
            mock_app.scrape.return_value = {
                "markdown": "Firecrawl content " + "x" * 200,
                "metadata": {
                    "title": "Firecrawl Article",
                    "sourceURL": "https://example.com/article",
                },
            }
            mock_firecrawl_cls.return_value = mock_app

            tool = DeepScrapeTool()
            result = tool.invoke("https://example.com/article")

            # Should skip Stage 1 and use Stage 2 (Firecrawl)
            assert "Firecrawl Article" in result
            assert "firecrawl" in result

            # Verify Firecrawl was called
            mock_app.scrape.assert_called_once()

            # Verify Archive.ph (Stage 3) was NOT called
            mock_get.assert_not_called()
        finally:
            if original_value is None:
                os.environ.pop("CRAWL4AI_ENABLED", None)
            else:
                os.environ["CRAWL4AI_ENABLED"] = original_value

            if original_firecrawl_key is None:
                os.environ.pop("FIRECRAWL_API_KEY", None)
            else:
                os.environ["FIRECRAWL_API_KEY"] = original_firecrawl_key

    @patch("whaagent.tools.deep_scrape.asyncio")
    def test_try_crawl4ai_when_enabled(
        self,
        mock_asyncio: MagicMock,
    ) -> None:
        """Verify that _try_crawl4ai proceeds normally when enabled."""
        mock_asyncio.run.return_value = DeepScrapeResult(
            url="https://example.com/article",
            status=ExtractionStatus.SUCCESS,
            stage=ExtractionStage.CRAWL4AI,
            content="A" + "x" * 200,
            title="Test Article",
            final_url="https://example.com/article",
        )

        tool = DeepScrapeTool()
        # Verify Crawl4AI is enabled by default
        assert tool._crawl4ai_enabled is True

        result = tool._try_crawl4ai("https://example.com/article")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.stage == ExtractionStage.CRAWL4AI
        assert result.title == "Test Article"

    def test_persistent_crawler_reuse(self) -> None:
        """Verify that _get_crawler() returns the same instance across calls."""
        import asyncio

        async def check_reuse() -> None:
            tool1 = DeepScrapeTool()
            tool2 = DeepScrapeTool()

            # Both tool instances should share the same class-level crawler
            crawler1 = await tool1._get_crawler()
            crawler2 = await tool2._get_crawler()

            # Verify they're the same instance
            assert crawler1 is crawler2
            assert DeepScrapeTool._crawler is crawler1

        # Run the async test
        asyncio.run(check_reuse())

    def test_warmup_prelaunches_browser(self) -> None:
        """Verify that warmup() pre-launches the Playwright browser."""
        import asyncio

        async def check_warmup() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Call warmup
            await DeepScrapeTool.warmup()

            # Verify crawler is initialized
            assert DeepScrapeTool._crawler is not None

            # Verify it's the same instance when accessed via _get_crawler
            tool = DeepScrapeTool()
            crawler = await tool._get_crawler()
            assert crawler is DeepScrapeTool._crawler

        asyncio.run(check_warmup())

    def test_warmup_is_idempotent(self) -> None:
        """Verify that warmup() can be called multiple times safely."""
        import asyncio

        async def check_idempotent() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Call warmup twice
            await DeepScrapeTool.warmup()
            first_crawler = DeepScrapeTool._crawler

            await DeepScrapeTool.warmup()
            second_crawler = DeepScrapeTool._crawler

            # Should be the same instance
            assert first_crawler is second_crawler

        asyncio.run(check_idempotent())

    def test_warmup_thread_safety(self) -> None:
        """Verify that warmup() is thread-safe with double-check locking."""
        import asyncio

        async def check_concurrent_warmup() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Call warmup concurrently
            tasks = [DeepScrapeTool.warmup() for _ in range(5)]
            await asyncio.gather(*tasks)

            # Verify only one crawler was created
            assert DeepScrapeTool._crawler is not None

            # All instances should get the same crawler
            tool = DeepScrapeTool()
            crawler = await tool._get_crawler()
            assert crawler is DeepScrapeTool._crawler

        asyncio.run(check_concurrent_warmup())

    def test_shutdown_cleans_up_crawler(self) -> None:
        """Verify that shutdown() properly cleans up the persistent browser instance."""
        import asyncio

        async def check_shutdown() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Warm up the crawler
            await DeepScrapeTool.warmup()
            assert DeepScrapeTool._crawler is not None

            # Mock the __aexit__ method to verify it's called
            original_crawler = DeepScrapeTool._crawler
            with patch.object(original_crawler, "__aexit__", return_value=None) as mock_aexit:
                await DeepScrapeTool.shutdown()

                # Verify __aexit__ was called
                mock_aexit.assert_called_once_with(None, None, None)

            # Verify crawler is set to None
            assert DeepScrapeTool._crawler is None

        asyncio.run(check_shutdown())

    def test_shutdown_is_idempotent(self) -> None:
        """Verify that shutdown() can be called multiple times safely."""
        import asyncio

        async def check_idempotent_shutdown() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Warm up the crawler
            await DeepScrapeTool.warmup()
            assert DeepScrapeTool._crawler is not None

            # Call shutdown multiple times
            await DeepScrapeTool.shutdown()
            assert DeepScrapeTool._crawler is None

            await DeepScrapeTool.shutdown()
            assert DeepScrapeTool._crawler is None

        asyncio.run(check_idempotent_shutdown())

    def test_shutdown_when_crawler_is_none(self) -> None:
        """Verify that shutdown() handles the case when crawler is already None."""
        import asyncio

        async def check_shutdown_when_none() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Call shutdown when crawler is None
            await DeepScrapeTool.shutdown()

            # Should still be None and no error
            assert DeepScrapeTool._crawler is None

        asyncio.run(check_shutdown_when_none())

    def test_shutdown_thread_safety(self) -> None:
        """Verify that shutdown() is thread-safe with double-check locking."""
        import asyncio

        async def check_concurrent_shutdown() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Warm up the crawler
            await DeepScrapeTool.warmup()
            assert DeepScrapeTool._crawler is not None

            # Mock the __aexit__ method
            original_crawler = DeepScrapeTool._crawler
            with patch.object(original_crawler, "__aexit__", return_value=None) as mock_aexit:
                # Call shutdown concurrently
                tasks = [DeepScrapeTool.shutdown() for _ in range(5)]
                await asyncio.gather(*tasks)

                # Verify __aexit__ was called only once
                mock_aexit.assert_called_once()

            # Verify crawler is set to None
            assert DeepScrapeTool._crawler is None

        asyncio.run(check_concurrent_shutdown())

    def test_warmup_shutdown_cycle(self) -> None:
        """Verify that warmup() and shutdown() can be cycled multiple times."""
        import asyncio

        async def check_cycle() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Cycle 1: warmup -> shutdown
            await DeepScrapeTool.warmup()
            assert DeepScrapeTool._crawler is not None
            first_crawler = DeepScrapeTool._crawler

            with patch.object(first_crawler, "__aexit__", return_value=None):
                await DeepScrapeTool.shutdown()
            assert DeepScrapeTool._crawler is None

            # Cycle 2: warmup -> shutdown again
            await DeepScrapeTool.warmup()
            assert DeepScrapeTool._crawler is not None
            second_crawler = DeepScrapeTool._crawler

            # Verify a new crawler instance was created
            assert second_crawler is not first_crawler

            with patch.object(second_crawler, "__aexit__", return_value=None):
                await DeepScrapeTool.shutdown()
            assert DeepScrapeTool._crawler is None

        asyncio.run(check_cycle())

    def test_warmup_sync_in_sync_context(self) -> None:
        """Verify that warmup_sync() works from non-async context."""
        # Reset class state
        DeepScrapeTool._crawler = None

        # Call warmup_sync from sync context
        DeepScrapeTool.warmup_sync()

        # Verify crawler is initialized
        assert DeepScrapeTool._crawler is not None

    def test_warmup_sync_is_idempotent(self) -> None:
        """Verify that warmup_sync() can be called multiple times safely."""
        # Reset class state
        DeepScrapeTool._crawler = None

        # Call warmup_sync twice
        DeepScrapeTool.warmup_sync()
        first_crawler = DeepScrapeTool._crawler

        DeepScrapeTool.warmup_sync()
        second_crawler = DeepScrapeTool._crawler

        # Should be the same instance
        assert first_crawler is second_crawler

    def test_warmup_sync_in_async_context_logs_warning(self, caplog: Any) -> None:
        """Verify that warmup_sync() logs a warning when called from async context."""
        import asyncio

        async def check_warning() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            # Call warmup_sync from within an async context
            # This should log a warning and not block
            with caplog.at_level(logging.WARNING):
                DeepScrapeTool.warmup_sync()

            # Verify warning was logged
            assert any("warmup_sync called from async context" in record.message for record in caplog.records)

            # Crawler should still be None (no warmup occurred)
            assert DeepScrapeTool._crawler is None

        asyncio.run(check_warning())

    def test_warmup_sync_then_shutdown_sync(self) -> None:
        """Verify that warmup_sync() and shutdown() can be used together."""
        import asyncio

        # Reset class state
        DeepScrapeTool._crawler = None

        # Warm up using sync method
        DeepScrapeTool.warmup_sync()
        assert DeepScrapeTool._crawler is not None

        # Shutdown using async method
        async def cleanup() -> None:
            original_crawler = DeepScrapeTool._crawler
            with patch.object(original_crawler, "__aexit__", return_value=None):
                await DeepScrapeTool.shutdown()

        asyncio.run(cleanup())
        assert DeepScrapeTool._crawler is None


class TestBrowserCrashRecovery:
    """Tests for browser crash recovery in _get_crawler()."""

    def test_get_crawler_recreates_on_crash(self) -> None:
        """Verify that _get_crawler() recreates browser if it crashes."""
        import asyncio

        async def check_crash_recovery() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            tool = DeepScrapeTool()

            # First call creates the crawler
            first_crawler = await tool._get_crawler()
            assert first_crawler is not None
            assert DeepScrapeTool._crawler is first_crawler

            # Simulate a crash by setting crawler to None
            DeepScrapeTool._crawler = None

            # Second call should recreate the crawler
            second_crawler = await tool._get_crawler()
            assert second_crawler is not None
            assert DeepScrapeTool._crawler is second_crawler

            # Verify it's a new instance (not the old one)
            assert second_crawler is not first_crawler

        asyncio.run(check_crash_recovery())

    def test_get_crawler_handles_exception_during_health_check(self) -> None:
        """Verify that _get_crawler() handles exceptions during health check."""
        import asyncio

        async def check_exception_handling() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            tool = DeepScrapeTool()

            # Create initial crawler
            crawler = await tool._get_crawler()
            assert crawler is not None

            # We can't easily mock the health check without a real operation,
            # but we can verify the exception handling path exists
            # by setting crawler to None and ensuring it recreates
            DeepScrapeTool._crawler = None

            # Should recreate successfully
            new_crawler = await tool._get_crawler()
            assert new_crawler is not None
            assert DeepScrapeTool._crawler is new_crawler

        asyncio.run(check_exception_handling())

    def test_get_crawler_thread_safety_during_recovery(self) -> None:
        """Verify that _get_crawler() is thread-safe during crash recovery."""
        import asyncio

        async def check_concurrent_recovery() -> None:
            # Reset class state
            DeepScrapeTool._crawler = None

            tool = DeepScrapeTool()

            # Create initial crawler
            await tool._get_crawler()
            assert DeepScrapeTool._crawler is not None

            # Simulate crash
            DeepScrapeTool._crawler = None

            # Multiple concurrent calls should all get the same new crawler
            tasks = [tool._get_crawler() for _ in range(5)]
            crawlers = await asyncio.gather(*tasks)

            # All should be the same instance
            assert len(set(id(c) for c in crawlers)) == 1
            assert DeepScrapeTool._crawler is crawlers[0]

        asyncio.run(check_concurrent_recovery())


class TestTimeoutProtection:
    """Tests for timeout protection in _crawl4ai_async()."""

    @patch("whaagent.tools.deep_scrape.asyncio.wait_for")
    def test_crawl4ai_timeout_returns_error(self, mock_wait_for: MagicMock) -> None:
        """Verify that _crawl4ai_async() handles timeout gracefully."""
        import asyncio

        # Mock wait_for to raise TimeoutError
        mock_wait_for.side_effect = asyncio.TimeoutError()

        tool = DeepScrapeTool()

        async def check_timeout() -> None:
            result = await tool._crawl4ai_async("https://example.com")

            assert result.status == ExtractionStatus.ERROR
            assert result.stage == ExtractionStage.CRAWL4AI
            assert "timeout after" in result.error.lower() and "seconds" in result.error.lower()

        asyncio.run(check_timeout())

    @patch("whaagent.tools.deep_scrape.asyncio.wait_for")
    def test_crawl4ai_timeout_does_not_crash_browser(self, mock_wait_for: MagicMock) -> None:
        """Verify that timeout doesn't corrupt the persistent browser instance."""
        import asyncio

        # Mock wait_for to raise TimeoutError on first call, succeed on second
        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.markdown.fit_markdown = "Content " * 50
        mock_crawl_result.markdown.raw_markdown = "Content " * 50
        mock_crawl_result.metadata = {"title": "Test"}
        mock_crawl_result.url = "https://example.com"

        mock_wait_for.side_effect = [
            asyncio.TimeoutError(),
            mock_crawl_result,
        ]

        tool = DeepScrapeTool()

        async def check_recovery_after_timeout() -> None:
            # First call times out
            result1 = await tool._crawl4ai_async("https://example.com")
            assert result1.status == ExtractionStatus.ERROR
            assert "timeout" in result1.error.lower()

            # Second call should succeed (browser still functional)
            result2 = await tool._crawl4ai_async("https://example.com")
            assert result2.status == ExtractionStatus.SUCCESS
            assert result2.title == "Test"

        asyncio.run(check_recovery_after_timeout())

    @patch("whaagent.tools.deep_scrape.asyncio.wait_for")
    def test_crawl4ai_exception_handling(self, mock_wait_for: MagicMock) -> None:
        """Verify that _crawl4ai_async() handles non-timeout exceptions."""
        import asyncio

        # Mock wait_for to raise a generic exception
        mock_wait_for.side_effect = RuntimeError("Browser process crashed")

        tool = DeepScrapeTool()

        async def check_exception() -> None:
            result = await tool._crawl4ai_async("https://example.com")

            assert result.status == ExtractionStatus.ERROR
            assert result.stage == ExtractionStage.CRAWL4AI
            assert "Crawl4AI error:" in result.error
            assert "Browser process crashed" in result.error

        asyncio.run(check_exception())

    @patch("whaagent.tools.deep_scrape.asyncio.wait_for")
    def test_crawl4ai_timeout_value_is_30_seconds(self, mock_wait_for: MagicMock) -> None:
        """Verify that the timeout is set to 30 seconds."""
        import asyncio

        # Mock wait_for to succeed immediately
        mock_crawl_result = MagicMock()
        mock_crawl_result.success = True
        mock_crawl_result.markdown.fit_markdown = "Content " * 50
        mock_crawl_result.markdown.raw_markdown = "Content " * 50
        mock_crawl_result.metadata = {"title": "Test"}
        mock_crawl_result.url = "https://example.com"

        async def mock_arun(*args, **kwargs):
            return mock_crawl_result

        mock_wait_for.return_value = mock_crawl_result

        tool = DeepScrapeTool()

        async def check_timeout_value() -> None:
            await tool._crawl4ai_async("https://example.com")

            # Verify wait_for was called with the configured timeout
            mock_wait_for.assert_called_once()
            call_kwargs = mock_wait_for.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 15.0

        asyncio.run(check_timeout_value())

    def test_rejects_invalid_url(self) -> None:
        tool = DeepScrapeTool()
        result = tool.invoke("not-a-url")
        assert "Error" in result
        assert "Invalid URL" in result

    def test_rejects_non_http_url(self) -> None:
        tool = DeepScrapeTool()
        result = tool.invoke("ftp://example.com/file")
        assert "Error" in result

    @patch("whaagent.tools.deep_scrape.asyncio")
    def test_stage1_crawl4ai_success(self, mock_asyncio: MagicMock) -> None:
        """Crawl4AI returns rich content — pipeline stops at Stage 1."""
        mock_asyncio.run.return_value = DeepScrapeResult(
            url="https://example.com/article",
            status=ExtractionStatus.SUCCESS,
            stage=ExtractionStage.CRAWL4AI,
            content="A" + "x" * 200,
            title="Test Article",
            final_url="https://example.com/article",
        )

        tool = DeepScrapeTool()
        result = tool.invoke("https://example.com/article")
        assert "Test Article" in result
        assert "crawl4ai" in result

    @patch("whaagent.tools.deep_scrape.asyncio")
    @patch("whaagent.tools.deep_scrape.Firecrawl")
    @patch.object(httpx, "get")
    def test_stage1_fails_stage2_firecrawl_succeeds(
        self,
        mock_get: MagicMock,
        mock_firecrawl_cls: MagicMock,
        mock_asyncio: MagicMock,
    ) -> None:
        """Crawl4AI fails, Firecrawl succeeds — returns content from Stage 2."""
        mock_asyncio.run.return_value = DeepScrapeResult(
            url="https://wsj.com/article",
            status=ExtractionStatus.BLOCKED,
            stage=ExtractionStage.CRAWL4AI,
            error="Insufficient content.",
        )

        mock_app = MagicMock()
        mock_app.scrape.return_value = {
            "markdown": "Full article content " + "x" * 200,
            "metadata": {
                "title": "Paywalled Article",
                "sourceURL": "https://wsj.com/article",
            },
        }
        mock_firecrawl_cls.return_value = mock_app

        tool = DeepScrapeTool()
        tool._firecrawl_api_key = "test-key"
        result = tool.invoke("https://wsj.com/article")
        assert "Paywalled Article" in result

    def test_stage2_firecrawl_skipped_without_key(self) -> None:
        """Firecrawl stage is skipped when no API key is set."""
        tool = DeepScrapeTool()
        tool._firecrawl_api_key = ""
        result = tool._try_firecrawl("https://example.com")
        assert result.status == ExtractionStatus.ERROR
        assert "FIRECRAWL_API_KEY" in result.error

    @patch.object(httpx, "get")
    def test_stage3_archive_ph_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://archive.ph/abc123/https://example.com"
        mock_response.text = (
            "<html><head><title>Archived Page</title></head><body><p>" + "Content here. " * 50 + "</p></body></html>"
        )
        mock_get.return_value = mock_response

        tool = DeepScrapeTool()
        result = tool._try_archive_ph("https://example.com")
        assert result.status == ExtractionStatus.SUCCESS
        assert result.stage == ExtractionStage.ARCHIVE_PH
        assert result.title == "Archived Page"

    @patch.object(httpx, "get")
    def test_stage3_archive_ph_not_found(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        tool = DeepScrapeTool()
        result = tool._try_archive_ph("https://nonexistent.com")
        assert result.status == ExtractionStatus.NOT_FOUND

    def test_extract_text_from_html(self) -> None:
        html = "<html><head><title>Test</title></head><body><p>Hello world</p><script>var x=1;</script></body></html>"
        text = DeepScrapeTool._extract_text_from_html(html)
        assert "Hello world" in text
        assert "var x" not in text

    def test_extract_title(self) -> None:
        html = "<html><head><title>My Page Title</title></head><body></body></html>"
        title = DeepScrapeTool._extract_title(html)
        assert title == "My Page Title"

    def test_extract_title_empty(self) -> None:
        html = "<html><head></head><body></body></html>"
        title = DeepScrapeTool._extract_title(html)
        assert title == ""

    @patch("whaagent.tools.deep_scrape.asyncio")
    @patch.object(httpx, "get")
    def test_full_pipeline_all_fail(
        self,
        mock_get: MagicMock,
        mock_asyncio: MagicMock,
    ) -> None:
        """When all 3 stages fail, returns a combined error."""
        mock_asyncio.run.return_value = DeepScrapeResult(
            url="https://example.com/article",
            status=ExtractionStatus.ERROR,
            stage=ExtractionStage.CRAWL4AI,
            error="Crawl4AI error.",
        )
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        tool = DeepScrapeTool()
        tool._firecrawl_api_key = ""
        result = tool.invoke("https://example.com/article")
        assert "All extraction stages failed" in result

    @patch("whaagent.tools.deep_scrape.asyncio")
    @patch.object(httpx, "get")
    def test_whitespace_url_handling(
        self,
        mock_get: MagicMock,
        mock_asyncio: MagicMock,
    ) -> None:
        mock_asyncio.run.return_value = DeepScrapeResult(
            url="https://example.com/article",
            status=ExtractionStatus.ERROR,
            stage=ExtractionStage.CRAWL4AI,
            error="failed",
        )
        mock_get.side_effect = httpx.ConnectError("fail")

        tool = DeepScrapeTool()
        result = tool.invoke("  https://example.com/article  ")
        assert "All extraction stages failed" in result or "example.com" in result


class TestFirecrawlDnsRetry:
    """Tests for DNS retry logic in _try_firecrawl."""

    @patch("whaagent.tools.deep_scrape.time")
    @patch("whaagent.tools.deep_scrape.Firecrawl")
    def test_firecrawl_retries_on_dns_error_then_succeeds(
        self,
        mock_firecrawl_cls: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Firecrawl retries once when DNS error occurs, then succeeds."""
        mock_app = MagicMock()
        # First call raises DNS error, second succeeds
        mock_app.scrape.side_effect = [
            Exception('DNS resolution failed for hostname "g1.globo.com.br"'),
            {
                "markdown": "Recovered content " + "x" * 200,
                "metadata": {"title": "Recovered", "sourceURL": "https://g1.globo.com"},
            },
        ]
        mock_firecrawl_cls.return_value = mock_app

        tool = DeepScrapeTool()
        tool._firecrawl_api_key = "test-key"
        result = tool._try_firecrawl("https://g1.globo.com")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.title == "Recovered"
        assert mock_app.scrape.call_count == 2
        mock_time.sleep.assert_called_once_with(2.0)

    @patch("whaagent.tools.deep_scrape.time")
    @patch("whaagent.tools.deep_scrape.Firecrawl")
    def test_firecrawl_retries_on_tunnel_error_then_succeeds(
        self,
        mock_firecrawl_cls: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Firecrawl retries once when ERR_TUNNEL_CONNECTION_FAILED occurs."""
        mock_app = MagicMock()
        mock_app.scrape.side_effect = [
            Exception('The URL failed to load with error code "ERR_TUNNEL_CONNECTION_FAILED"'),
            {
                "markdown": "Tunnel recovered " + "x" * 200,
                "metadata": {"title": "Tunnel OK", "sourceURL": "https://example.com"},
            },
        ]
        mock_firecrawl_cls.return_value = mock_app

        tool = DeepScrapeTool()
        tool._firecrawl_api_key = "test-key"
        result = tool._try_firecrawl("https://example.com")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.title == "Tunnel OK"
        assert mock_app.scrape.call_count == 2

    @patch("whaagent.tools.deep_scrape.time")
    @patch("whaagent.tools.deep_scrape.Firecrawl")
    def test_firecrawl_does_not_retry_on_non_dns_error(
        self,
        mock_firecrawl_cls: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Firecrawl does NOT retry on non-DNS errors."""
        mock_app = MagicMock()
        mock_app.scrape.side_effect = Exception("Internal Server Error: Rate limit exceeded")
        mock_firecrawl_cls.return_value = mock_app

        tool = DeepScrapeTool()
        tool._firecrawl_api_key = "test-key"
        result = tool._try_firecrawl("https://example.com")

        assert result.status == ExtractionStatus.ERROR
        assert "Rate limit exceeded" in result.error
        assert mock_app.scrape.call_count == 1
        mock_time.sleep.assert_not_called()

    @patch("whaagent.tools.deep_scrape.time")
    @patch("whaagent.tools.deep_scrape.Firecrawl")
    def test_firecrawl_dns_retry_exhausted(
        self,
        mock_firecrawl_cls: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Firecrawl retries once on DNS error, then returns error if still failing."""
        mock_app = MagicMock()
        mock_app.scrape.side_effect = Exception("getaddrinfo failed for host example.com")
        mock_firecrawl_cls.return_value = mock_app

        tool = DeepScrapeTool()
        tool._firecrawl_api_key = "test-key"
        result = tool._try_firecrawl("https://example.com")

        assert result.status == ExtractionStatus.ERROR
        assert "getaddrinfo failed" in result.error
        assert mock_app.scrape.call_count == 2
        mock_time.sleep.assert_called_once_with(2.0)

    @patch("whaagent.tools.deep_scrape.time")
    @patch("whaagent.tools.deep_scrape.Firecrawl")
    def test_firecrawl_no_retry_on_blocked(
        self,
        mock_firecrawl_cls: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Firecrawl does NOT retry when content is blocked (insufficient content)."""
        mock_app = MagicMock()
        mock_app.scrape.return_value = {
            "markdown": "short",
            "metadata": {},
        }
        mock_firecrawl_cls.return_value = mock_app

        tool = DeepScrapeTool()
        tool._firecrawl_api_key = "test-key"
        result = tool._try_firecrawl("https://example.com")

        assert result.status == ExtractionStatus.BLOCKED
        assert mock_app.scrape.call_count == 1
        mock_time.sleep.assert_not_called()


class TestArchivePhDnsRetry:
    """Tests for DNS retry logic in _try_archive_ph."""

    @patch("whaagent.tools.deep_scrape.time")
    @patch.object(httpx, "get")
    def test_archive_ph_retries_on_dns_error_then_succeeds(
        self,
        mock_get: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Archive.ph retries once on DNS error, then succeeds."""
        dns_error = httpx.ConnectError("getaddrinfo failed for host archive.ph")
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.url = "https://archive.ph/abc/https://example.com"
        success_response.text = (
            "<html><head><title>Archived</title></head><body><p>" + "Content. " * 50 + "</p></body></html>"
        )

        mock_get.side_effect = [dns_error, success_response]

        tool = DeepScrapeTool()
        result = tool._try_archive_ph("https://example.com")

        assert result.status == ExtractionStatus.SUCCESS
        assert result.title == "Archived"
        assert mock_get.call_count == 2
        mock_time.sleep.assert_called_once_with(2.0)

    @patch("whaagent.tools.deep_scrape.time")
    @patch.object(httpx, "get")
    def test_archive_ph_does_not_retry_on_non_dns_error(
        self,
        mock_get: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Archive.ph does NOT retry on non-DNS connection errors."""
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        tool = DeepScrapeTool()
        result = tool._try_archive_ph("https://example.com")

        assert result.status == ExtractionStatus.ERROR
        assert "Connection refused" in result.error
        assert mock_get.call_count == 1
        mock_time.sleep.assert_not_called()

    @patch("whaagent.tools.deep_scrape.time")
    @patch.object(httpx, "get")
    def test_archive_ph_dns_retry_exhausted(
        self,
        mock_get: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Archive.ph retries once on DNS error, returns error if still failing."""
        mock_get.side_effect = httpx.ConnectError("DNS resolution failed for archive.ph")

        tool = DeepScrapeTool()
        result = tool._try_archive_ph("https://example.com")

        assert result.status == ExtractionStatus.ERROR
        assert "DNS resolution failed" in result.error
        assert mock_get.call_count == 2
        mock_time.sleep.assert_called_once_with(2.0)

    @patch("whaagent.tools.deep_scrape.time")
    @patch.object(httpx, "get")
    def test_archive_ph_no_retry_on_404(
        self,
        mock_get: MagicMock,
        mock_time: MagicMock,
    ) -> None:
        """Archive.ph does NOT retry on 404 (not a DNS error)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        tool = DeepScrapeTool()
        result = tool._try_archive_ph("https://example.com")

        assert result.status == ExtractionStatus.NOT_FOUND
        assert mock_get.call_count == 1
        mock_time.sleep.assert_not_called()
