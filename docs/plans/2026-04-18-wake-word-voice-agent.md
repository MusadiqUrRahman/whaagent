# Wake Word for Voice-Activated WhatsApp Assistant

**Date:** 2026-04-18
**Status:** Planning

## Problem

Currently, audio messages received via WhatsApp are transcribed but the transcription is returned directly to the user without agent processing. We want a "wake word" feature: when a user says the assistant's name (e.g., "Jarvis, what's the weather?"), the system should recognize the wake word, strip it, and process the remaining text through the agent graph. Audio without the wake word should be ignored.

## Current Audio Flow

1. User sends voice message via WhatsApp
2. Go gateway (`gateway/message.go`) detects audio message via `extractAudioMessage()`
3. Go gateway calls `forwardAudioToPythonAPI()` which POSTs multipart form to `/api/v1/channels/whatsapp/audio`
4. Python API (`src/whaagent/api/routes/whatsapp.py:whatsapp_audio_webhook`) receives audio, transcribes via Groq Whisper, caches transcription
5. Currently returns raw transcription as response -- **no agent processing**

## Proposed Flow

1-4. (same as above)
5. After transcription, check if tenant has a `wake_word` configured
6. If `wake_word` is set and found in transcription (case-insensitive):
   - Strip the wake word from the text
   - Route the remaining text through the agent graph (same as `whatsapp_webhook` does for text messages)
   - Return the agent's response
7. If `wake_word` is set but NOT found:
   - Return a brief acknowledgment (or empty response with a flag so Go gateway can skip sending)
8. If `wake_word` is NOT configured for tenant:
   - Process the transcription through the agent unconditionally (current behavior for text messages)

## Config Changes

Add `wake_word` field to `WhatsAppTenantConfig`:

```yaml
# .whaagent.yaml
whatsapp:
  tenants:
    - id: "primary"
      phone: "+5511999999999"
      default_agent: "assistant"
      wake_word: "Jarvis"        # NEW: voice activation keyword
    - id: "secondary"
      phone: "+1555000000"
      default_agent: "assistant"
      # wake_word not set = all audio goes to agent
```

- `wake_word: "Jarvis"` -- only process audio containing "Jarvis"
- `wake_word` unset/null -- all audio goes to agent (backward compatible)
- Wake word check is case-insensitive

## Files to Modify

1. **`src/whaagent/config.py`** -- Add `wake_word: str | None = None` to `WhatsAppTenantConfig` dataclass; parse it in `from_dict()`
2. **`src/whaagent/services/wake_word.py`** -- NEW: Wake word detection utility
3. **`src/whaagent/api/routes/whatsapp.py`** -- Modify `whatsapp_audio_webhook()` to check wake word after transcription and route to agent if matched
4. **`src/whaagent/config.example.yaml`** -- Document `wake_word` field
5. **`tests/test_wake_word.py`** -- NEW: Tests for wake word detection
6. **`tests/test_api/test_audio_route.py`** -- Add tests for wake word routing in audio endpoint

## Wake Word Detection Logic (`services/wake_word.py`)

```python
def check_wake_word(text: str, wake_word: str | None) -> tuple[bool, str]:
    """Check if text contains the wake word.

    Returns:
        (matched, cleaned_text) where matched is True if wake word found,
        and cleaned_text has the wake word stripped from the beginning.
    """
```

- Case-insensitive matching
- Strips wake word from beginning of text (with optional comma/colon separator)
- If `wake_word` is None/empty, returns `(True, text)` (no restriction)

## Test Plan

1. **Unit tests for `check_wake_word()`:**
   - Wake word at start: "Jarvis what's the weather" -> (True, "what's the weather")
   - Wake word with comma: "Jarvis, what's the weather" -> (True, "what's the weather")
   - Wake word mid-sentence: "Hey Jarvis tell me" -> (True, "tell me")
   - Case insensitive: "jarvis hello" -> (True, "hello")
   - No wake word: "hello there" -> (False, "hello there")
   - None wake word -> (True, original text)
   - Empty text -> (False, "")

2. **Audio endpoint tests:**
   - Audio with wake word -> agent processes and returns response
   - Audio without wake word -> returns acknowledgment, no agent call
   - Tenant with no wake word configured -> always processes through agent
   - Cached transcription + wake word -> still checks wake word

3. **Config parsing tests:**
   - Parse wake_word from YAML
   - Default wake_word is None
