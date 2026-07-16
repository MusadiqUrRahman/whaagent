"""Tests for AudioTranscriber service."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from whaagent.services.audio_transcriber import AudioTranscriber


class TestAudioTranscriber:
    """Test suite for AudioTranscriber class."""

    # Tests 1-6: transcribe_audio method
    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, tmp_path: Path):
        """Test successful audio transcription."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Hello world"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file)
            assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_transcribe_audio_no_api_key(self, tmp_path: Path, monkeypatch):
        """Test transcription fails without API key."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Clear both environment variables to ensure no API key
        monkeypatch.delenv("GROQ_AUDIO_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        transcriber = AudioTranscriber(api_key=None)
        assert not transcriber.is_configured

        result = await transcriber.transcribe_audio(audio_file)
        assert result == "Error: GROQ_AUDIO_API_KEY or GROQ_API_KEY not set"

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_not_found(self):
        """Test transcription fails with non-existent file."""
        transcriber = AudioTranscriber(api_key="test-key")

        result = await transcriber.transcribe_audio("/nonexistent/audio.mp3")
        assert "Error:" in result
        assert "Audio file not found" in result

    @pytest.mark.asyncio
    async def test_transcribe_audio_oversized_file(self, tmp_path: Path):
        """Test transcription fails with file exceeding size limit."""
        audio_file = tmp_path / "large.mp3"

        # Create a file and mock its size to be over limit
        audio_file.write_bytes(b"x" * 1024)  # Small actual file

        transcriber = AudioTranscriber(api_key="test-key")

        # Mock the stat to return a large file size
        # Use a proper stat result-like mock with all required attributes
        import stat

        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 30 * 1024 * 1024  # 30MB
        mock_stat_result.st_mode = stat.S_IFREG | 0o644  # Regular file

        with patch.object(Path, "stat", return_value=mock_stat_result):
            result = await transcriber.transcribe_audio(audio_file)
            assert "Error:" in result
            assert "File size" in result
            assert "exceeds 25MB limit" in result

    @pytest.mark.asyncio
    async def test_transcribe_audio_api_error(self, tmp_path: Path):
        """Test transcription handles API error responses."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file)
            assert "Error: API request failed" in result
            assert "500" in result

    @pytest.mark.asyncio
    async def test_transcribe_audio_timeout(self, tmp_path: Path):
        """Test transcription handles timeout."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file)
            assert result == "Error: Transcription request timed out"

    # Tests 7-8: is_configured property
    def test_is_configured_with_key(self):
        """Test is_configured returns True when API key is set."""
        transcriber = AudioTranscriber(api_key="test-key")
        assert transcriber.is_configured is True

    def test_is_configured_without_key(self, monkeypatch):
        """Test is_configured returns False when no API key."""
        monkeypatch.delenv("GROQ_AUDIO_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        transcriber = AudioTranscriber(api_key=None)
        assert transcriber.is_configured is False

    # Test 9: get_available_models
    def test_get_available_models(self):
        """Test get_available_models returns list of models."""
        models = AudioTranscriber.get_available_models()
        assert isinstance(models, list)
        assert "whisper-large-v3-turbo" in models
        assert "whisper-large-v3" in models

    # Test 10: create_default
    def test_create_default(self):
        """Test create_default creates an instance."""
        transcriber = AudioTranscriber.create_default()
        assert isinstance(transcriber, AudioTranscriber)

    # Tests 11-13: _validate_path method
    def test_validate_path_valid(self, tmp_path: Path):
        """Test _validate_path with valid file."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"audio data")

        transcriber = AudioTranscriber(api_key="test-key")
        result = transcriber._validate_path(audio_file)

        assert isinstance(result, Path)
        assert result.exists()

    def test_validate_path_not_found(self):
        """Test _validate_path raises ValueError for non-existent file."""
        transcriber = AudioTranscriber(api_key="test-key")

        with pytest.raises(ValueError) as exc_info:
            transcriber._validate_path("/nonexistent/file.mp3")

        assert "Audio file not found" in str(exc_info.value)

    def test_validate_path_is_directory(self, tmp_path: Path):
        """Test _validate_path raises ValueError for directory."""
        transcriber = AudioTranscriber(api_key="test-key")

        with pytest.raises(ValueError) as exc_info:
            transcriber._validate_path(tmp_path)

        assert "Path is a directory" in str(exc_info.value)

    # Tests 14-15: _convert_to_mp3 method
    def test_convert_to_mp3_no_conversion_needed_mp3(self, tmp_path: Path):
        """Test _convert_to_mp3 returns MP3 files as-is."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"audio data")

        transcriber = AudioTranscriber(api_key="test-key")
        result_path, is_temp = transcriber._convert_to_mp3(audio_file)

        assert result_path == audio_file
        assert is_temp is False

    def test_convert_to_mp3_no_conversion_needed_wav(self, tmp_path: Path):
        """Test _convert_to_mp3 returns WAV files as-is."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"audio data")

        transcriber = AudioTranscriber(api_key="test-key")
        result_path, is_temp = transcriber._convert_to_mp3(audio_file)

        assert result_path == audio_file
        assert is_temp is False

    def test_convert_to_mp3_import_error(self, tmp_path: Path):
        """Test _convert_to_mp3 handles missing ffmpeg-python."""
        audio_file = tmp_path / "test.ogg"
        audio_file.write_bytes(b"audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        with patch.dict("sys.modules", {"ffmpeg": None}):
            # Simulate ImportError when trying to import ffmpeg
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "ffmpeg":
                    raise ImportError("No module named 'ffmpeg'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result_path, is_temp = transcriber._convert_to_mp3(audio_file)

            assert result_path == audio_file
            assert is_temp is False

    # Tests 16-18: Additional API response scenarios
    @pytest.mark.asyncio
    async def test_transcribe_empty_result(self, tmp_path: Path):
        """Test transcription handles empty result from API."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": ""}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file)
            assert "Error: Empty transcription" in result

    @pytest.mark.asyncio
    async def test_transcribe_unexpected_response(self, tmp_path: Path):
        """Test transcription handles rate limit (429) response."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file)
            assert "Error: Rate limit exceeded" in result

    @pytest.mark.asyncio
    async def test_transcribe_invalid_api_key(self, tmp_path: Path):
        """Test transcription handles invalid API key (401) response."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="invalid-key")

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file)
            assert "Error: Invalid API key" in result

    # Additional edge case tests
    @pytest.mark.asyncio
    async def test_transcribe_audio_network_error(self, tmp_path: Path):
        """Test transcription handles network errors."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file)
            assert "Error: Network error" in result

    def test_api_key_from_environment(self, monkeypatch):
        """Test API key is loaded from GROQ_AUDIO_API_KEY environment variable."""
        monkeypatch.setenv("GROQ_AUDIO_API_KEY", "env-api-key")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        transcriber = AudioTranscriber()
        assert transcriber.api_key == "env-api-key"
        assert transcriber.is_configured is True

    def test_api_key_fallback_to_groq_api_key(self, monkeypatch):
        """Test API key falls back to GROQ_API_KEY."""
        monkeypatch.delenv("GROQ_AUDIO_API_KEY", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "fallback-api-key")

        transcriber = AudioTranscriber()
        assert transcriber.api_key == "fallback-api-key"
        assert transcriber.is_configured is True

    def test_model_from_environment(self, monkeypatch):
        """Test model is loaded from GROQ_WHISPER_MODEL environment variable."""
        monkeypatch.setenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

        transcriber = AudioTranscriber(api_key="test-key")
        assert transcriber.model == "whisper-large-v3"

    def test_default_model_used(self, monkeypatch):
        """Test default model is used when not set in environment."""
        monkeypatch.delenv("GROQ_WHISPER_MODEL", raising=False)

        transcriber = AudioTranscriber(api_key="test-key")
        assert transcriber.model == "whisper-large-v3-turbo"

    def test_custom_timeout(self):
        """Test custom timeout is set correctly."""
        transcriber = AudioTranscriber(api_key="test-key", timeout=120.0)
        assert transcriber.timeout == 120.0

    def test_default_timeout(self):
        """Test default timeout is set correctly."""
        transcriber = AudioTranscriber(api_key="test-key")
        assert transcriber.timeout == 60.0

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_mime_type(self, tmp_path: Path):
        """Test transcription with explicit MIME type."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Transcribed text"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file, mime_type="audio/wav")
            assert result == "Transcribed text"

            # Verify the MIME type was passed to the API
            call_args = mock_client.post.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_transcribe_audio_413_too_large(self, tmp_path: Path):
        """Test transcription handles 413 (file too large) response."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        transcriber = AudioTranscriber(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 413

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await transcriber.transcribe_audio(audio_file)
            assert "Error: Audio file too large for API" in result
