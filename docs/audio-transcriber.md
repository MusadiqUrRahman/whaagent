# Audio Transcriber

The Audio Transcriber provides high-quality audio transcription using Groq's ultra-fast Whisper models. It's designed for WhatsApp agents but can be used standalone.

## Overview

The `AudioTranscriber` is a standalone class that provides:
- Ultra-fast transcription (~30-50ms for 30s audio with whisper-large-v3-turbo)
- Support for multiple audio formats (.wav, .mp3, .ogg, .oga, .m4a, .webm, .flac, .wma)
- Automatic format conversion to MP3 when needed
- Comprehensive error handling (returns error messages as strings)
- Path validation for security

## Available Models

| Model | Speed | Use Case |
|-------|-------|----------|
| `whisper-large-v3-turbo` | ~30-50ms | Default, faster, good quality |
| `whisper-large-v3` | ~100-150ms | Slower, higher accuracy |

## Environment Variables

| Variable | Required | Description |
|----------|-----------|-------------|
| `GROQ_AUDIO_API_KEY` | Yes | Your Groq API key (get free account at console.groq.com) |
| `GROQ_API_KEY` | Yes | Alternative to GROQ_AUDIO_API_KEY (fallback) |
| `GROQ_WHISPER_MODEL` | No | Model name (default: whisper-large-v3-turbo) |

## Supported Audio Formats

- `.wav` - WAV format (no conversion needed)
- `.mp3` - MP3 format (no conversion needed)
- `.ogg` - OGG format (converted to MP3)
- `.oga` - OGG audio format (converted to MP3)
- `.m4a` - M4A format (converted to MP3)
- `.webm` - WebM format (converted to MP3)
- `.flac` - FLAC format (converted to MP3)
- `.wma` - WMA format (converted to MP3)

## File Size Limits

- **Maximum file size:** 25MB
- **Recommended size:** Under 10MB for optimal performance
- **Transcription duration:** Whisper handles up to 30 seconds effectively

## Dependencies

For audio format conversion (formats other than .wav and .mp3):
- `pydub` - Audio conversion library
- `ffmpeg` - Required by pydub for audio processing

Install:
```bash
uv add pydub
# Install ffmpeg via your package manager
# macOS: brew install ffmpeg
# Ubuntu: sudo apt-get install ffmpeg
```

## Usage

### Basic Usage

```python
from whaagent.services.audio_transcriber import AudioTranscriber

# Create transcriber (reads GROQ_AUDIO_API_KEY or GROQ_API_KEY from environment)
transcriber = AudioTranscriber()

# Transcribe audio file
transcription = await transcriber.transcribe_audio("voice_message.mp3")

# Check for errors
if transcription.startswith("Error:"):
    print(f"Failed: {transcription}")
else:
    print(f"Transcription: {transcription}")
```

### With Custom Model

```python
transcriber = AudioTranscriber(
    api_key="your-api-key",
    model="whisper-large-v3",  # Slower but more accurate
    timeout=120.0,  # Longer timeout for large files
)
```

### Check Configuration

```python
transcriber = AudioTranscriber()

if not transcriber.is_configured:
    print("API key not set!")

# Get available models
models = transcriber.get_available_models()
print(f"Available models: {models}")
```

## Error Messages

All errors are returned as strings with "Error:" prefix for easy identification:

| Error | Cause | Solution |
|-------|--------|----------|
| `GROQ_AUDIO_API_KEY or GROQ_API_KEY not set` | Environment variable missing | Set `GROQ_AUDIO_API_KEY` |
| `exceeds maximum allowed size` | File larger than 25MB | Compress or trim audio |
| `Cannot convert format` | Unsupported audio format | Install `pydub` and `ffmpeg` |
| `not found` | Audio file doesn't exist | Check file path |
| `timed out` | API request took too long | Increase timeout or check network |
| `Network error` | Connection failed | Check internet connection |

## Performance Tips

1. **Use MP3 format** when possible - no conversion overhead
2. **Compressed MP3 (128k)** - Good balance of quality and speed
3. **Turbo model** for most use cases - faster with good accuracy
4. **Large model** only when needed - for difficult audio or important content

## Integration with WhatsApp Agent

The WhatsApp agent automatically uses `AudioTranscriber` for audio messages. No additional configuration needed beyond setting `GROQ_AUDIO_API_KEY` or `GROQ_API_KEY`.

## Getting a Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Create a free account
3. Generate an API key
4. Set as environment variable: `export GROQ_AUDIO_API_KEY=gsk-your-key-here`

Free tier includes generous limits for transcription use.
