"""Tests for whaagent package - YouTube transcript module."""

from unittest.mock import MagicMock, patch

from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from whaagent.tools.youtube_transcript import YouTubeTranscriptTool


class TestYouTubeTranscriptTool:
    """Test YouTubeTranscriptTool."""

    def test_youtube_transcript_tool_name(self):
        """Test tool has correct name."""
        tool = YouTubeTranscriptTool()
        assert tool.name == "youtube_transcript"

    def test_youtube_transcript_tool_description(self):
        """Test tool has description."""
        tool = YouTubeTranscriptTool()
        assert tool.description is not None
        assert "Extracts transcript/subtitles" in tool.description

    def test_extract_video_id_direct(self):
        """Test extracting direct 11-character video ID."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_short_url(self):
        """Test extracting video ID from youtu.be URL."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_watch_url(self):
        """Test extracting video ID from watch URL."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_embed_url(self):
        """Test extracting video ID from embed URL."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_v_url(self):
        """Test extracting video ID from v/ URL."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("https://www.youtube.com/v/dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_shorts_url(self):
        """Test extracting video ID from shorts URL."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_video_id_with_dashes(self):
        """Test extracting video ID with dashes."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("abc-def_123")
        assert video_id == "abc-def_123"

    def test_extract_video_id_invalid_url(self):
        """Test extracting video ID from invalid URL."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("https://example.com/video")
        assert video_id is None

    def test_extract_video_id_too_short(self):
        """Test extracting video ID that's too short."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("abc")
        assert video_id is None

    def test_extract_video_id_too_long(self):
        """Test extracting video ID that's too long."""
        tool = YouTubeTranscriptTool()
        video_id = tool._extract_video_id("abcdefghijk123456")
        assert video_id is None

    def test_format_timestamp_under_hour(self):
        """Test formatting timestamp under 1 hour."""
        tool = YouTubeTranscriptTool()
        timestamp = tool._format_timestamp(90.5)
        assert timestamp == "01:30"

    def test_format_timestamp_exact_hour(self):
        """Test formatting timestamp exactly 1 hour."""
        tool = YouTubeTranscriptTool()
        timestamp = tool._format_timestamp(3600.0)
        assert timestamp == "01:00:00"

    def test_format_timestamp_over_hour(self):
        """Test formatting timestamp over 1 hour."""
        tool = YouTubeTranscriptTool()
        timestamp = tool._format_timestamp(3661.0)
        assert timestamp == "01:01:01"

    def test_format_timestamp_multiple_hours(self):
        """Test formatting timestamp with multiple hours."""
        tool = YouTubeTranscriptTool()
        timestamp = tool._format_timestamp(7325.0)
        assert timestamp == "02:02:05"

    def test_format_transcript(self):
        """Test formatting transcript entries."""
        tool = YouTubeTranscriptTool()
        transcript = [
            {"start": 0.0, "text": "Hello world"},
            {"start": 10.5, "text": "Second line"},
            {"start": 61.0, "text": "After a minute"},
        ]
        result = tool._format_transcript(transcript)

        assert "[00:00] Hello world" in result
        assert "[00:10] Second line" in result
        assert "[01:01] After a minute" in result

    def test_format_transcript_empty_text(self):
        """Test formatting transcript with empty text entries."""
        tool = YouTubeTranscriptTool()
        transcript = [
            {"start": 0.0, "text": "Valid text"},
            {"start": 10.0, "text": ""},  # Empty text
            {"start": 20.0, "text": "  "},  # Whitespace only
        ]
        result = tool._format_transcript(transcript)

        # Should only include non-empty text
        lines = result.split("\n")
        assert len([line for line in lines if "Valid text" in line]) == 1

    def test_error_invalid_url_message(self):
        """Test invalid URL error message."""
        tool = YouTubeTranscriptTool()
        error = tool._error_invalid_url("https://bad-url.com/video")

        assert "Could not extract video ID" in error
        assert "https://bad-url.com/video" in error

    def test_error_transcripts_disabled_message(self):
        """Test transcripts disabled error message."""
        tool = YouTubeTranscriptTool()
        error = tool._error_transcripts_disabled()

        assert "transcripts/captions disabled" in error

    def test_error_video_unavailable_message(self):
        """Test video unavailable error message."""
        tool = YouTubeTranscriptTool()
        error = tool._error_video_unavailable("https://youtube.com/watch?v=123")

        assert "Video 'https://youtube.com/watch?v=123' is unavailable" in error

    def test_error_no_transcript_message(self):
        """Test no transcript found error message."""
        tool = YouTubeTranscriptTool()
        error = tool._error_no_transcript()

        assert "No transcript found" in error


class TestYouTubeTranscriptToolIntegration:
    """Test YouTubeTranscriptTool integration with cache and API."""

    def test_invoke_success_with_cache(self):
        """Test invoke with cached transcript."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"transcript_text": "cached transcript", "video_id": "test123"}

        tool = YouTubeTranscriptTool(cache=mock_cache)

        with patch("whaagent.tools.youtube_transcript.YouTubeTranscriptCache", return_value=mock_cache):
            result = tool.invoke("https://youtube.com/watch?v=test123")

            assert result == "cached transcript"
            mock_cache.get.assert_called_once_with("test123")

    def test_invoke_force_refresh_bypasses_cache(self):
        """Test invoke with force_refresh bypasses cache."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"transcript_text": "cached transcript", "video_id": "test123"}

        tool = YouTubeTranscriptTool(cache=mock_cache)

        mock_transcript = [{"start": 0.0, "text": "fresh transcript"}]

        with (
            patch("whaagent.tools.youtube_transcript.YouTubeTranscriptApi") as mock_api,
            patch.object(tool, "_fetch_transcript", return_value=mock_transcript),
        ):
            result = tool.invoke("https://youtube.com/watch?v=test123", force_refresh=True)

            assert "fresh transcript" in result
            assert mock_api is not None  # Use the variable
            mock_cache.get.assert_not_called()

    def test_invoke_transcripts_disabled(self):
        """Test invoke handles TranscriptsDisabled exception."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        tool = YouTubeTranscriptTool(cache=mock_cache)

        with patch.object(tool, "_fetch_transcript", side_effect=TranscriptsDisabled("test123")):
            result = tool.invoke("https://youtube.com/watch?v=test123")

            assert "transcripts/captions disabled" in result

    def test_invoke_video_unavailable(self):
        """Test invoke handles VideoUnavailable exception."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        tool = YouTubeTranscriptTool(cache=mock_cache)

        with patch.object(tool, "_fetch_transcript", side_effect=VideoUnavailable("test123")):
            result = tool.invoke("https://youtube.com/watch?v=test123")

            assert "Video 'https://youtube.com/watch?v=test123' is unavailable" in result

    def test_invoke_no_transcript_found(self):
        """Test invoke handles NoTranscriptFound exception."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        tool = YouTubeTranscriptTool(cache=mock_cache)

        with patch.object(tool, "_fetch_transcript", side_effect=NoTranscriptFound("test123", [], None)):
            result = tool.invoke("https://youtube.com/watch?v=test123")

            assert "No transcript found" in result

    def test_invoke_stores_in_cache(self):
        """Test invoke stores fetched transcript in cache."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        tool = YouTubeTranscriptTool(cache=mock_cache)

        mock_transcript = [{"start": 0.0, "text": "fetched transcript"}]

        with patch.object(tool, "_fetch_transcript", return_value=mock_transcript):
            tool.invoke("https://youtube.com/watch?v=test123")

            mock_cache.set.assert_called_once()
            call_kwargs = mock_cache.set.call_args[1]
            assert call_kwargs["video_id"] == "test123"
            assert "fetched transcript" in call_kwargs["transcript_text"]

    def test_invoke_invalid_url(self):
        """Test invoke with invalid URL."""
        mock_cache = MagicMock()
        tool = YouTubeTranscriptTool(cache=mock_cache)

        result = tool.invoke("https://invalid-url.com/video")

        assert "Could not extract video ID" in result
        mock_cache.get.assert_not_called()

    def test_fetch_transcript_with_language_fallback(self):
        """Test _fetch_transcript with language fallback."""
        tool = YouTubeTranscriptTool()

        mock_api = MagicMock()
        mock_list = MagicMock()

        # First language fails, second succeeds
        def find_transcript_side_effect(langs):
            if "en-US" in str(langs):
                raise NoTranscriptFound("test", ["en-US"], None)
            return MagicMock(
                fetch=MagicMock(
                    return_value=MagicMock(to_raw_data=MagicMock(return_value=[{"start": 0.0, "text": "en"}]))
                )
            )

        mock_list.find_transcript = MagicMock(side_effect=find_transcript_side_effect)
        mock_api.list.return_value = mock_list

        with patch("whaagent.tools.youtube_transcript.YouTubeTranscriptApi", return_value=mock_api):
            result = tool._fetch_transcript("test123")
            assert len(result) > 0

    def test_fetch_transcript_translates_if_needed(self):
        """Test _fetch_transcript translates to English if needed."""
        tool = YouTubeTranscriptTool()

        mock_api = MagicMock()
        mock_list = MagicMock()
        mock_list.find_transcript = MagicMock(side_effect=NoTranscriptFound("test", [], None))

        # Simulate translation path
        mock_transcript = MagicMock(
            translate=MagicMock(
                return_value=MagicMock(
                    fetch=MagicMock(
                        return_value=MagicMock(
                            to_raw_data=MagicMock(return_value=[{"start": 0.0, "text": "translated"}])
                        )
                    )
                )
            )
        )
        mock_list.__iter__ = MagicMock(return_value=iter([mock_transcript]))
        mock_api.list.return_value = mock_list

        with patch("whaagent.tools.youtube_transcript.YouTubeTranscriptApi", return_value=mock_api):
            result = tool._fetch_transcript("test123")
            assert len(result) > 0
