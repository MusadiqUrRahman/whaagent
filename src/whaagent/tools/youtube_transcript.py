"""YouTube transcript extraction tool using youtube-transcript-api."""

import logging
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from whaagent.interfaces.base import Tool
from whaagent.tools.youtube_cache import YouTubeTranscriptCache

logger = logging.getLogger(__name__)


class YouTubeTranscriptTool(Tool):
    """Extract transcripts/subtitles from YouTube videos with local caching.

    This tool fetches video transcripts using youtube-transcript-api,
    supporting multiple languages with automatic fallback and translation.

    Features:
        - Extract transcripts from any YouTube video with captions
        - Multi-language support with priority fallback
        - Automatic translation to target language
        - Timestamp-aware output
        - Video metadata inclusion
        - Local caching to avoid repeated API calls

    Usage Examples:
        "https://youtube.com/watch?v=dQw4w9WgXcQ"
        "Summarize this video: https://youtu.be/dQw4w9WgXcQ"

    Error Handling:
        - Invalid URL: Returns clear error message
        - No captions: Suggests alternatives
        - Video unavailable: Returns appropriate error
    """

    # Language priority for transcript fetching
    DEFAULT_LANGUAGES = ["en", "en-US", "en-GB"]
    FALLBACK_LANGUAGES = ["es", "pt", "fr", "de", "it", "ja", "ko", "zh-Hans"]

    def __init__(self, cache: YouTubeTranscriptCache | None = None) -> None:
        """Initialize the tool with optional cache.

        Args:
            cache: Optional cache instance. If None, creates default cache.
        """
        self._cache = cache or YouTubeTranscriptCache()

    @property
    def name(self) -> str:
        """Return the name of this tool."""
        return "youtube_transcript"

    @property
    def description(self) -> str:
        """Return a description of what this tool does."""
        return (
            "Extracts transcript/subtitles from a YouTube video. "
            "Input should be a YouTube URL or video ID. "
            "Returns full transcript text with timestamps."
        )

    def invoke(self, input_str: str, force_refresh: bool = False) -> str:
        """Extract transcript from a YouTube video URL or ID.

        Args:
            input_str: YouTube URL (various formats) or video ID.
            force_refresh: If True, bypass cache and fetch fresh transcript.

        Returns:
            Transcript text with timestamps, or error message.
        """
        try:
            video_id = self._extract_video_id(input_str)
            if video_id is None:
                return self._error_invalid_url(input_str)

            # Check cache first (unless force refresh)
            if not force_refresh:
                cached = self._cache.get(video_id)
                if cached is not None:
                    logger.info(f"Retrieved transcript from cache: {video_id}")
                    return cast(str, cached["transcript_text"])

            # Fetch from API
            transcript = self._fetch_transcript(video_id)
            formatted = self._format_transcript(transcript)

            # Store in cache
            self._cache.set(
                video_id=video_id,
                transcript_text=formatted,
                video_url=input_str,
                language="en",  # Default language for now
            )

            return formatted

        except TranscriptsDisabled:
            return self._error_transcripts_disabled()
        except VideoUnavailable:
            return self._error_video_unavailable(input_str)
        except NoTranscriptFound:
            return self._error_no_transcript()
        except Exception as e:
            return f"Error: Unexpected error extracting transcript: {e}"

    def _extract_video_id(self, url_or_id: str) -> str | None:
        """Extract video ID from various YouTube URL formats or direct ID.

        Supports:
            - https://www.youtube.com/watch?v=VIDEO_ID
            - https://youtu.be/VIDEO_ID
            - https://www.youtube.com/embed/VIDEO_ID
            - https://www.youtube.com/v/VIDEO_ID
            - VIDEO_ID (direct 11-character ID)

        Args:
            url_or_id: A YouTube URL in any supported format, or an
                11-character video ID.

        Returns:
            The 11-character video ID, or None if extraction fails.

        Examples:
            >>> tool._extract_video_id("https://youtu.be/abc123")
            'abc123'
            >>> tool._extract_video_id("invalid")
            None
        """
        url_or_id = url_or_id.strip()

        # Direct video ID (11 characters, alphanumeric with - and _)
        if len(url_or_id) == 11 and all(c.isalnum() or c in "-_" for c in url_or_id):
            return url_or_id

        try:
            parsed = urlparse(url_or_id)

            # youtu.be short format
            if parsed.hostname in ("youtu.be", "www.youtu.be"):
                return parsed.path.lstrip("/")

            # youtube.com formats
            if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
                # /watch?v=VIDEO_ID
                if parsed.path == "/watch":
                    query = parse_qs(parsed.query)
                    return query.get("v", [None])[0]

                # /embed/VIDEO_ID or /v/VIDEO_ID
                if parsed.path.startswith(("/embed/", "/v/")):
                    return parsed.path.split("/")[2]

                # /shorts/VIDEO_ID
                if parsed.path.startswith(("/shorts/")):
                    return parsed.path.split("/")[2]

        except Exception:
            pass

        return None

    def _fetch_transcript(self, video_id: str) -> list[dict[str, Any]]:
        """Fetch transcript with language fallback.

        Args:
            video_id: The 11-character YouTube video ID.

        Returns:
            List of transcript entries with text, start, and duration.

        Raises:
            NoTranscriptFound: If no transcript is available in any supported language.
        """
        all_languages = self.DEFAULT_LANGUAGES + self.FALLBACK_LANGUAGES

        try:
            # Create API instance
            api = YouTubeTranscriptApi()

            # Try to get transcript in preferred languages
            transcript_list = api.list(video_id)

            for lang in all_languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    fetched = transcript.fetch()
                    return fetched.to_raw_data()  # Convert to list of dicts
                except NoTranscriptFound:
                    continue

            # Try any available transcript with translation
            for transcript in transcript_list:
                fetched = transcript.translate("en").fetch()
                return fetched.to_raw_data()  # Convert to list of dicts

        except Exception:
            # Fallback: try direct fetch
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=all_languages)
            return fetched.to_raw_data()  # Convert to list of dicts

        # Raise NoTranscriptFound with all required parameters
        raise NoTranscriptFound(video_id, all_languages, None)

    def _format_transcript(self, transcript: list[dict[str, Any]]) -> str:
        """Format transcript entries into readable text with timestamps.

        Args:
            transcript: List of transcript entries with text, start, and duration.

        Returns:
            Formatted transcript with timestamps.
        """
        lines = []
        for entry in transcript:
            timestamp = self._format_timestamp(entry.get("start", 0))
            text = entry.get("text", "").strip()
            if text:
                lines.append(f"[{timestamp}] {text}")
        return "\n".join(lines)

    def _format_timestamp(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format.

        Args:
            seconds: Time in seconds.

        Returns:
            Formatted timestamp string.
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _error_invalid_url(self, url: str) -> str:
        """Return error message for invalid URL.

        Args:
            url: The invalid URL.

        Returns:
            Formatted error message.
        """
        return (
            f"Error: Could not extract video ID from '{url}'. "
            "Please provide a valid YouTube URL (e.g., "
            "https://www.youtube.com/watch?v=VIDEO_ID) or an 11-character video ID."
        )

    def _error_transcripts_disabled(self) -> str:
        """Return error message for disabled transcripts.

        Returns:
            Formatted error message.
        """
        return (
            "Error: This video has transcripts/captions disabled. "
            "The creator has not made subtitles available for this video."
        )

    def _error_video_unavailable(self, url: str) -> str:
        """Return error message for unavailable video.

        Args:
            url: The unavailable video URL.

        Returns:
            Formatted error message.
        """
        return f"Error: Video '{url}' is unavailable. It may be private, deleted, or region-restricted."

    def _error_no_transcript(self) -> str:
        """Return error message when no transcript is found.

        Returns:
            Formatted error message.
        """
        return "Error: No transcript found for this video. The video may not have captions in a supported language."
