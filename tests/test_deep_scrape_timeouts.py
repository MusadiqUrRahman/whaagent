"""Tests for deep_scrape timeout configuration and fallback behavior."""

import os
from unittest.mock import patch

from whaagent.tools.deep_scrape import (
    DeepScrapeResult,
    DeepScrapeTool,
    ExtractionStage,
    ExtractionStatus,
)


class TestTimeoutDefaults:
    """Tests for timeout default values at import time."""

    def test_default_crawl4ai_timeout_is_15(self):
        """Default Crawl4AI timeout should be 15 seconds."""
        from whaagent.tools.deep_scrape import _CRAWL4AI_TIMEOUT

        assert _CRAWL4AI_TIMEOUT == 15.0

    def test_default_firecrawl_timeout_is_30(self):
        """Default Firecrawl timeout should be 30 seconds."""
        from whaagent.tools.deep_scrape import _FIRECRAWL_TIMEOUT

        assert _FIRECRAWL_TIMEOUT == 30.0


class TestCrawl4AIFallback:
    """Tests for Crawl4AI failure triggering Firecrawl fallback."""

    @patch.dict(os.environ, {"FIRECRAWL_API_KEY": "test-key"})
    def test_crawl4ai_disabled_skips_to_firecrawl(self):
        """When Crawl4AI is disabled, extraction falls through to Firecrawl."""
        tool = DeepScrapeTool()
        tool._crawl4ai_enabled = False

        with (
            patch.object(tool, "_try_crawl4ai") as mock_c4ai,
            patch.object(tool, "_try_firecrawl") as mock_fc,
        ):
            mock_c4ai.return_value = DeepScrapeResult(
                url="https://example.com",
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.CRAWL4AI,
                error="Crawl4AI disabled",
            )
            mock_fc.return_value = DeepScrapeResult(
                url="https://example.com",
                status=ExtractionStatus.SUCCESS,
                stage=ExtractionStage.FIRECRAWL,
                content="test content that is long enough to pass the check",
            )

            result = tool._extract("https://example.com")

            mock_c4ai.assert_called_once()
            mock_fc.assert_called_once()
            assert result.status == ExtractionStatus.SUCCESS
            assert result.stage == ExtractionStage.FIRECRAWL

    @patch.dict(os.environ, {"FIRECRAWL_API_KEY": "test-key"})
    def test_full_pipeline_tries_all_stages(self):
        """All three stages are attempted when each fails."""
        tool = DeepScrapeTool()

        with (
            patch.object(tool, "_try_crawl4ai") as mock_c4ai,
            patch.object(tool, "_try_firecrawl") as mock_fc,
            patch.object(tool, "_try_archive_ph") as mock_archive,
        ):
            error_result = DeepScrapeResult(
                url="https://example.com",
                status=ExtractionStatus.ERROR,
                error="failed",
            )
            mock_c4ai.return_value = error_result
            mock_fc.return_value = error_result
            mock_archive.return_value = error_result

            result = tool._extract("https://example.com")

            mock_c4ai.assert_called_once()
            mock_fc.assert_called_once()
            mock_archive.assert_called_once()
            assert result.status == ExtractionStatus.ERROR
