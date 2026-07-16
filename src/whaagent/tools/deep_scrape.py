"""Web content extraction tool with cascading fallback pipeline.

Implements a 3-stage hybrid strategy for extracting web content,
including paywalled and bot-protected sites:

Stage 1: Crawl4AI (local Python library, free, fast — handles 80% of cases)
Stage 2: Firecrawl API (credit-based, handles Cloudflare/turnstile)
Stage 3: Archive.ph (free, archived snapshots — last resort)
"""

import asyncio
import concurrent.futures
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

import httpx
from firecrawl import Firecrawl  # type: ignore[import-untyped]

from whaagent.interfaces.base import Tool

if TYPE_CHECKING:
    from crawl4ai import AsyncWebCrawler, BrowserConfig

logger = logging.getLogger(__name__)

# Module-level persistent crawler instance
_crawler_instance: "AsyncWebCrawler | None" = None
_crawler_lock = asyncio.Lock()
_crawler_initialized = False

# Patterns that indicate transient DNS or tunnel connection failures.
_DNS_ERROR_PATTERNS = (
    "DNS resolution failed",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "getaddrinfo failed",
    "Name or service not known",
    "nodename nor servname provided",
    "Temporary failure in name resolution",
)

_MAX_DNS_RETRIES = 1  # One retry after initial attempt (2 total attempts)
_DNS_RETRY_DELAY_SECONDS = 2.0

# Configurable timeouts (seconds) — override via environment variables
_CRAWL4AI_TIMEOUT = float(os.environ.get("CRAWL4AI_TIMEOUT", "15"))
_FIRECRAWL_TIMEOUT = float(os.environ.get("FIRECRAWL_TIMEOUT", "30"))


class ExtractionStage(str, Enum):
    """Which extraction method succeeded."""

    CRAWL4AI = "crawl4ai"
    FIRECRAWL = "firecrawl"
    ARCHIVE_PH = "archive_ph"


class ExtractionStatus(str, Enum):
    """Result status."""

    SUCCESS = "success"
    BLOCKED = "blocked"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class DeepScrapeResult:
    """Structured result from web content extraction.

    Attributes:
        url: The original URL requested.
        final_url: The URL after redirects (may differ from original).
        status: Whether extraction succeeded.
        stage: Which extraction method was used.
        content: Extracted markdown content (empty string on failure).
        title: Page title if extracted.
        error: Error message if status is not SUCCESS.
    """

    url: str
    status: ExtractionStatus
    stage: ExtractionStage | None = None
    content: str = ""
    title: str = ""
    final_url: str = ""
    error: str = ""

    def __str__(self) -> str:
        if self.status == ExtractionStatus.SUCCESS:
            header = f"# {self.title}\n\n" if self.title else ""
            stage_value = self.stage.value if self.stage else "unknown"
            meta = f"[Source: {stage_value} | URL: {self.final_url or self.url}]\n\n"
            return f"{meta}{header}{self.content}"
        return f"Error extracting {self.url}: {self.error}"


def _is_dns_error(error_message: str) -> bool:
    """Check if an error message indicates a DNS or tunnel connection failure.

    Args:
        error_message: The error string to inspect.

    Returns:
        True if the error is DNS-related and potentially transient.
    """
    msg_lower = error_message.lower()
    return any(pattern.lower() in msg_lower for pattern in _DNS_ERROR_PATTERNS)


def _retry_on_dns_error(
    stage_label: str,
    attempt_fn: Callable[[], DeepScrapeResult],
) -> DeepScrapeResult:
    """Retry a single-attempt extraction function once on DNS-related errors.

    Args:
        stage_label: Human-readable stage name for log messages (e.g. "Stage 2 (Firecrawl)").
        attempt_fn: Callable that takes no arguments and returns a DeepScrapeResult.

    Returns:
        The first successful result, or the last error result if all attempts fail.
    """
    for attempt in range(_MAX_DNS_RETRIES + 1):
        result = attempt_fn()
        if result.status == ExtractionStatus.SUCCESS:
            return result
        if attempt < _MAX_DNS_RETRIES and _is_dns_error(result.error):
            logger.info(
                "[deep_scrape] %s: DNS error on attempt %d, retrying in %.1fs — %s",
                stage_label,
                attempt + 1,
                _DNS_RETRY_DELAY_SECONDS,
                result.error,
            )
            time.sleep(_DNS_RETRY_DELAY_SECONDS)
            continue
        return result
    return result  # unreachable, but satisfies mypy


class DeepScrapeTool(Tool):
    """Extract web content using a cascading fallback pipeline.

    Tries Crawl4AI first (local library, free), then Firecrawl API
    (credit-based), then Archive.ph (free archive) as a last resort.
    """

    # Class-level state for persistent browser
    _crawler: ClassVar["AsyncWebCrawler | None"] = None
    _crawler_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self) -> None:
        self._firecrawl_api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        self._firecrawl_url = os.environ.get("FIRECRAWL_URL", "https://api.firecrawl.dev/v2")
        self._crawl4ai_enabled = os.environ.get("CRAWL4AI_ENABLED", "true").lower() == "true"
        self._persistent = os.environ.get("PLAYWRIGHT_PERSISTENT", "true").lower() == "true"

    @classmethod
    def is_persistent(cls) -> bool:
        """Return True if the browser should be kept alive between requests."""
        return os.environ.get("PLAYWRIGHT_PERSISTENT", "true").lower() == "true"

    @classmethod
    async def warmup(cls) -> None:
        """Pre-launch the Playwright browser for faster first request.

        Call this during application startup to eliminate cold-start latency.
        """
        if cls._crawler is not None:
            return  # Already warmed

        async with cls._crawler_lock:
            if cls._crawler is not None:
                return

            from crawl4ai import AsyncWebCrawler

            browser_config = cls._get_browser_config()
            cls._crawler = AsyncWebCrawler(config=browser_config)
            await cls._crawler.__aenter__()
            logger.info("[deep_scrape] Playwright browser warmed up")

    @classmethod
    async def shutdown(cls) -> None:
        """Clean up the persistent browser instance.

        Call this during application shutdown.
        """
        if cls._crawler is None:
            return

        async with cls._crawler_lock:
            if cls._crawler is None:
                return

            await cls._crawler.__aexit__(None, None, None)
            cls._crawler = None
            logger.info("[deep_scrape] Playwright browser shut down")

    @classmethod
    def warmup_sync(cls) -> None:
        """Synchronous warmup wrapper for non-async contexts.

        Provides a blocking interface for warming up the browser from
        synchronous code paths (e.g., script entry points).
        """
        try:
            asyncio.get_running_loop()
            # Already in async context — can't block
            logger.warning("[deep_scrape] warmup_sync called from async context, use warmup() instead")
        except RuntimeError:
            # No event loop — safe to create one
            asyncio.run(cls.warmup())

    async def _get_crawler(self) -> "AsyncWebCrawler":
        """Get or create the persistent AsyncWebCrawler instance with recovery."""
        if DeepScrapeTool._crawler is not None:
            try:
                # Quick health check — verify the crawler is still alive
                # We can't easily check browser health without an operation,
                # but we can at least verify the object exists
                return DeepScrapeTool._crawler
            except Exception:
                # Browser crashed, recreate
                logger.warning("[deep_scrape] Browser appears dead, recreating...")
                DeepScrapeTool._crawler = None

        async with DeepScrapeTool._crawler_lock:
            # Double-check after acquiring lock
            if DeepScrapeTool._crawler is not None:
                return DeepScrapeTool._crawler

            from crawl4ai import AsyncWebCrawler

            browser_config = self._get_browser_config()
            DeepScrapeTool._crawler = AsyncWebCrawler(config=browser_config)
            await DeepScrapeTool._crawler.__aenter__()
            return DeepScrapeTool._crawler

    @staticmethod
    def _get_browser_config() -> "BrowserConfig":
        """Build BrowserConfig with optional low-memory optimizations.

        Returns:
            BrowserConfig instance configured based on PLAYWRIGHT_LOW_MEMORY env var.
        """
        from crawl4ai import BrowserConfig

        browser_config = BrowserConfig(
            headless=True,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
                "Safari/537.36"
            ),
        )

        # Add memory-conscious flags for low-memory systems
        if os.environ.get("PLAYWRIGHT_LOW_MEMORY", "false").lower() == "true":
            logger.info("[deep_scrape] PLAYWRIGHT_LOW_MEMORY=true: enabling memory optimizations")
            browser_config.extra_args = [
                "--disable-dev-shm-usage",  # Avoid /dev/shm (often small on containers)
                "--disable-gpu",  # Disable GPU acceleration
                "--no-sandbox",  # Disable sandbox (use with caution)
                "--disable-setuid-sandbox",  # Disable setuid sandbox
                "--disable-background-timer-throttling",  # Disable background timer throttling
                "--disable-backgrounding-occluded-windows",  # Disable backgrounding occluded windows
                "--disable-renderer-backgrounding",  # Disable renderer backgrounding
            ]

        return browser_config

    @property
    def name(self) -> str:
        return "deep_scrape"

    @property
    def description(self) -> str:
        return (
            "Extract clean text content from a web page URL, including paywalled "
            "and bot-protected sites. Returns markdown-formatted content. "
            "Input: a single URL string."
        )

    def invoke(self, input_str: str) -> str:
        """Extract content from the given URL using the cascading pipeline."""
        url = input_str.strip()
        if not url.startswith(("http://", "https://")):
            return f"Error: Invalid URL — must start with http:// or https://. Got: {url}"

        result = self._extract(url)
        return str(result)

    def _extract(self, url: str) -> DeepScrapeResult:
        """Run the 3-stage extraction pipeline."""
        # Stage 1: Crawl4AI (local library, free)
        result = self._try_crawl4ai(url)
        logger.info("[deep_scrape] Stage 1 (Crawl4AI): status=%s error=%s", result.status.value, result.error)
        if result.status == ExtractionStatus.SUCCESS:
            return result

        # Stage 2: Firecrawl (API, credit-based)
        result = self._try_firecrawl(url)
        logger.info("[deep_scrape] Stage 2 (Firecrawl): status=%s error=%s", result.status.value, result.error)
        if result.status == ExtractionStatus.SUCCESS:
            return result

        # Stage 3: Archive.ph (free, last resort)
        result = self._try_archive_ph(url)
        logger.info("[deep_scrape] Stage 3 (Archive.ph): status=%s error=%s", result.status.value, result.error)
        if result.status == ExtractionStatus.SUCCESS:
            return result

        # All stages failed — return last error
        logger.warning("[deep_scrape] All 3 stages failed for %s", url)
        return DeepScrapeResult(
            url=url,
            status=ExtractionStatus.ERROR,
            error="All extraction stages failed. Site may be down or fully paywalled.",
        )

    # --- Stage 1: Crawl4AI (Python library) ---

    def _try_crawl4ai(self, url: str) -> DeepScrapeResult:
        """Try Crawl4AI Python library (local, headless browser)."""
        if not self._crawl4ai_enabled:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.CRAWL4AI,
                error="Crawl4AI disabled via CRAWL4AI_ENABLED=false",
            )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Already in an event loop — run in a separate thread
            return self._try_crawl4ai_sync_fallback(url)

        try:
            return asyncio.run(self._crawl4ai_async(url))
        except ImportError:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.CRAWL4AI,
                error="crawl4ai package not installed. Run: uv add crawl4ai",
            )
        except Exception as e:
            err_msg = str(e)
            if "Executable doesn't exist" in err_msg or "playwright install" in err_msg.lower():
                err_msg = "Playwright browser not installed. Run: make install"
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.CRAWL4AI,
                error=err_msg,
            )

    async def _crawl4ai_async(self, url: str) -> DeepScrapeResult:
        """Async Crawl4AI extraction using v0.8.x API."""
        from crawl4ai import CrawlerRunConfig  # type: ignore
        from crawl4ai.content_filter_strategy import PruningContentFilter  # type: ignore
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator  # type: ignore

        md_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.45,
                threshold_type="dynamic",
                min_word_threshold=5,
            )
        )
        run_config = CrawlerRunConfig(markdown_generator=md_generator)

        try:
            if self._persistent:
                crawler = await self._get_crawler()
                result = await asyncio.wait_for(
                    crawler.arun(url=url, config=run_config),
                    timeout=_CRAWL4AI_TIMEOUT,
                )
            else:
                # Ephemeral: create and destroy browser per request (~540 MB saved at idle)
                from crawl4ai import AsyncWebCrawler

                async with AsyncWebCrawler(config=self._get_browser_config()) as crawler:
                    result = await asyncio.wait_for(
                        crawler.arun(url=url, config=run_config),
                        timeout=_CRAWL4AI_TIMEOUT,
                    )
        except asyncio.TimeoutError:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.CRAWL4AI,
                error=f"Crawl4AI timeout after {_CRAWL4AI_TIMEOUT:.0f} seconds",
            )
        except Exception as e:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.CRAWL4AI,
                error=f"Crawl4AI error: {str(e)}",
            )

        if not result.success:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.CRAWL4AI,
                error=result.error_message or "Crawl4AI failed.",
            )
        fit = result.markdown.fit_markdown or ""
        raw = result.markdown.raw_markdown or ""
        # fit_markdown can be too aggressive on non-standard layouts — fall back
        # to raw if it pruned more than 80% of the content
        if fit and raw and len(fit) < len(raw) * 0.2:
            content = raw
        else:
            content = fit or raw
        if not content or len(content.strip()) < 100:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.BLOCKED,
                stage=ExtractionStage.CRAWL4AI,
                error="Crawl4AI returned insufficient content (possibly blocked).",
            )
        title = result.metadata.get("title", "") if result.metadata else ""
        return DeepScrapeResult(
            url=url,
            status=ExtractionStatus.SUCCESS,
            stage=ExtractionStage.CRAWL4AI,
            content=content,
            title=title,
            final_url=result.url,
        )

    def _try_crawl4ai_sync_fallback(self, url: str) -> DeepScrapeResult:
        """Fallback when already inside an event loop — run in a thread."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, self._crawl4ai_async(url))
            try:
                return future.result(timeout=45)
            except Exception as e:
                return DeepScrapeResult(
                    url=url,
                    status=ExtractionStatus.ERROR,
                    stage=ExtractionStage.CRAWL4AI,
                    error=str(e),
                )

    # --- Stage 2: Firecrawl ---

    def _try_firecrawl(self, url: str) -> DeepScrapeResult:
        """Try Firecrawl API via firecrawl-py SDK (requires FIRECRAWL_API_KEY).

        Retries once on DNS-related errors to handle transient network failures.
        """
        if not self._firecrawl_api_key:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.FIRECRAWL,
                error="FIRECRAWL_API_KEY not set — skipping Firecrawl stage.",
            )

        return _retry_on_dns_error("Stage 2 (Firecrawl)", lambda: self._firecrawl_attempt(url))

    def _firecrawl_attempt(self, url: str) -> DeepScrapeResult:
        """Single attempt at Firecrawl extraction.

        Args:
            url: The URL to scrape.

        Returns:
            DeepScrapeResult with extraction outcome.
        """
        try:
            app = Firecrawl(api_key=self._firecrawl_api_key, api_url=self._firecrawl_url)

            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = pool.submit(lambda: app.scrape(url, formats=["markdown"], only_main_content=True))
            try:
                result = future.result(timeout=_FIRECRAWL_TIMEOUT)
            except concurrent.futures.TimeoutError:
                return DeepScrapeResult(
                    url=url,
                    status=ExtractionStatus.ERROR,
                    stage=ExtractionStage.FIRECRAWL,
                    error=f"Firecrawl timeout after {_FIRECRAWL_TIMEOUT:.0f} seconds",
                )
            finally:
                pool.shutdown(wait=False)
            content = result.get("markdown", "") if isinstance(result, dict) else str(result)
            if not content or len(content.strip()) < 100:
                return DeepScrapeResult(
                    url=url,
                    status=ExtractionStatus.BLOCKED,
                    stage=ExtractionStage.FIRECRAWL,
                    error="Firecrawl returned insufficient content.",
                )
            metadata = result.get("metadata", {}) if isinstance(result, dict) else {}
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.SUCCESS,
                stage=ExtractionStage.FIRECRAWL,
                content=content,
                title=metadata.get("title", ""),
                final_url=metadata.get("sourceURL", url),
            )
        except Exception as e:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.FIRECRAWL,
                error=f"Firecrawl error: {e}",
            )

    # --- Stage 3: Archive.ph ---

    def _try_archive_ph(self, url: str) -> DeepScrapeResult:
        """Try Archive.ph for an archived snapshot.

        Retries once on connection/DNS errors to handle transient failures.
        """
        return _retry_on_dns_error("Stage 3 (Archive.ph)", lambda: self._archive_ph_attempt(url))

    def _archive_ph_attempt(self, url: str) -> DeepScrapeResult:
        """Single attempt at Archive.ph extraction.

        Args:
            url: The URL to look up in the archive.

        Returns:
            DeepScrapeResult with extraction outcome.
        """
        try:
            check_url = f"https://archive.ph/newest/{url}"
            response = httpx.get(
                check_url,
                follow_redirects=True,
                timeout=20.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
                        "Safari/537.36"
                    ),
                },
            )
            if response.status_code != 200:
                return DeepScrapeResult(
                    url=url,
                    status=ExtractionStatus.NOT_FOUND,
                    stage=ExtractionStage.ARCHIVE_PH,
                    error="No archive found on archive.ph.",
                )

            text = self._extract_text_from_html(response.text)
            if not text or len(text.strip()) < 100:
                return DeepScrapeResult(
                    url=url,
                    status=ExtractionStatus.BLOCKED,
                    stage=ExtractionStage.ARCHIVE_PH,
                    error="Archive.ph returned insufficient content.",
                )

            title = self._extract_title(response.text)

            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.SUCCESS,
                stage=ExtractionStage.ARCHIVE_PH,
                content=text,
                title=title,
                final_url=str(response.url),
            )
        except Exception as e:
            return DeepScrapeResult(
                url=url,
                status=ExtractionStatus.ERROR,
                stage=ExtractionStage.ARCHIVE_PH,
                error=str(e),
            )

    @staticmethod
    def _extract_text_from_html(html: str) -> str:
        """Extract readable text from HTML using a simple heuristic."""
        # Remove script and style blocks
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Decode common HTML entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&quot;", '"').replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")
        return text

    @staticmethod
    def _extract_title(html: str) -> str:
        """Extract <title> content from HTML."""
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
