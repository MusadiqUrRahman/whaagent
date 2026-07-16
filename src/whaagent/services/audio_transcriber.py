"""Audio transcription service using Groq Whisper API.

This module provides audio transcription using Groq's Whisper models.
Supports multiple audio formats and handles automatic conversion.

Environment Variables:
    GROQ_AUDIO_API_KEY: Primary Groq API key for audio transcription
    GROQ_API_KEY: Fallback Groq API key
    GROQ_WHISPER_MODEL: Model name (default: whisper-large-v3-turbo)

Performance:
    - whisper-large-v3-turbo: ~30-50ms for 30s audio
    - whisper-large-v3: ~100-150ms in 30s audio
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS: frozenset[str] = frozenset({".wav", ".mp3", ".ogg", ".oga", ".m4a", ".webm", ".flac", ".wma"})

_AVAILABLE_MODELS = ["whisper-large-v3-turbo", "whisper-large-v3"]
_DEFAULT_MODEL = "whisper-large-v3-turbo"

_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_MAX_SIZE_MB = 25
_DEFAULT_TIMEOUT = 60.00


class AudioTranscriber:
    """Audio transcription service using Groq Whisper API.

    Provides ultra-fast transcription (~30-50ms for 30s audio)
    using Groq's Whisper models. Supports multiple audio formats and
    handles automatic conversion via ffmpeg-python.

    Attributes:
        api_key: Groq API key.
        model: Whisper model name.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize AudioTranscriber.

        Args:
            api_key: Groq API key. Falls back to GROQ_AUDIO_API_KEY / GROQ_API_KEY.
            model: Whisper model name. Falls back to GROQ_WHISPER_MODEL.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key or os.getenv("GROQ_AUDIO_API_KEY") or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_WHISPER_MODEL", _DEFAULT_MODEL)
        self.timeout = timeout

        if not self.api_key:
            logger.warning("GROQ_AUDIO_API_KEY or GROQ_API_KEY not set - transcriptions will fail")

    @property
    def is_configured(self) -> bool:
        """Check if the transcriber has an API key configured."""
        return bool(self.api_key)

    @staticmethod
    def get_available_models() -> list[str]:
        """Get list of available Whisper models."""
        return list(_AVAILABLE_MODELS)

    @classmethod
    def create_default(cls) -> "AudioTranscriber":
        """Create a transcriber with default configuration."""
        return cls()

    def _validate_path(self, audio_path: str | Path) -> Path:
        """Validate audio file path exists and is a file."""
        path = Path(audio_path).resolve()
        if not path.exists():
            raise ValueError(f"Audio file not found: {path}")
        if path.is_dir():
            raise ValueError(f"Path is a directory: {path}")
        return path

    def _convert_to_mp3(self, input_path: Path) -> tuple[Path, bool]:
        """Convert audio to MP3 if needed via ffmpeg-python.

        Returns:
            Tuple of (output_path, is_temporary).
        """
        suffix = input_path.suffix.lower()
        if suffix in {".mp3", ".wav"}:
            return input_path, False

        try:
            import ffmpeg  # type: ignore[import-untyped]

            output_path = Path(tempfile.mktemp(suffix=".mp3"))
            (
                ffmpeg.input(str(input_path))
                .output(str(output_path), acodec="libmp3lame", audio_bitrate="128k")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, quiet=True)
            )
            logger.info("Converted %s to MP3: %s", suffix, output_path)
            return output_path, True
        except ImportError:
            logger.error("ffmpeg-python not installed - cannot convert audio format")
            return input_path, False
        except Exception as e:
            logger.error("Failed to convert audio: %s", e)
            return input_path, False

    async def transcribe_audio(
        self,
        audio_path: str | Path,
        mime_type: str | None = None,
    ) -> str:
        """Transcribe an audio file using Groq Whisper API.

        Args:
            audio_path: Path to the audio file.
            mime_type: MIME type (optional, auto-detected from extension).

        Returns:
            Transcription text, Error message starting with "Error:" on failure.
        """
        if not self.is_configured:
            return "Error: GROQ_AUDIO_API_KEY or GROQ_API_KEY not set"

        try:
            validated_path = self._validate_path(audio_path)
        except ValueError as e:
            return f"Error: {e}"

        file_size_mb = validated_path.stat().st_size / (1024 * 1024)
        if file_size_mb > _MAX_SIZE_MB:
            return f"Error: File size ({file_size_mb:.1f}MB) exceeds {_MAX_SIZE_MB}MB limit"

        audio_file_path, is_temp = self._convert_to_mp3(validated_path)

        try:
            mime_map = {
                "audio/mpeg": ".mp3",
                "audio/mp3": ".mp3",
                "audio/wav": ".wav",
                "audio/ogg": ".ogg",
                "audio/opus": ".ogg",
                "audio/mp4": ".m4a",
                "audio/webm": ".webm",
                "audio/flac": ".flac",
            }
            ext = mime_map.get(mime_type or "", audio_file_path.suffix)

            with open(audio_file_path, "rb") as f:
                audio_data = f.read()

            files = {"file": (f"audio{ext}", audio_data, mime_type or "audio/mpeg")}
            data = {"model": self.model}
            headers = {"Authorization": f"Bearer {self.api_key}"}

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(_API_URL, files=files, data=data, headers=headers)

            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                transcription = result.get("text", "")
                if not transcription:
                    return "Error: Empty transcription result from API"
                logger.info("Transcribed audio (%d chars)", len(transcription))
                return str(transcription)
            elif response.status_code == 401:
                return "Error: Invalid API key"
            elif response.status_code == 429:
                return "Error: Rate limit exceeded"
            elif response.status_code == 413:
                return "Error: Audio file too large for API"
            else:
                return f"Error: API request failed with status {response.status_code}"

        except httpx.TimeoutException:
            return "Error: Transcription request timed out"
        except httpx.NetworkError as e:
            return f"Error: Network error - {e}"
        except Exception as e:
            return f"Error: {e}"
        finally:
            if is_temp:
                try:
                    audio_file_path.unlink(missing_ok=True)
                except Exception:
                    pass
