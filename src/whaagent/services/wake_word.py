"""Wake word detection for voice-activated assistant.

Provides case-insensitive wake word matching with text stripping.
Used by the WhatsApp audio endpoint to determine whether a transcribed
voice message should be forwarded to the agent graph.

Configuration:
    Set ``wake_word`` per tenant in ``.whaagent.yaml``:

    .. code-block:: yaml

        whatsapp:
          tenants:
            - id: personal
              phone: "+5511999999999"
              wake_word: "Jarvis"

    When ``wake_word`` is unset (None), all audio is forwarded to the agent
    (backward-compatible behaviour).
"""

import re


def check_wake_word(text: str, wake_word: str | None) -> tuple[bool, str]:
    """Check whether *text* contains the configured *wake_word*.

    The match is case-insensitive.  When the wake word is found it is
    stripped from the text together with any leading separator
    (comma, colon, dash, or whitespace) so that the remaining text is
    ready to be forwarded to the agent.

    Args:
        text: The transcribed speech.
        wake_word: The expected wake word (e.g. ``"Jarvis"``).  Pass
            ``None`` to disable wake-word gating (always matches).

    Returns:
        A ``(matched, cleaned_text)`` tuple.

        * ``matched`` is ``True`` when the wake word was detected (or
          when *wake_word* is ``None``/empty, meaning no restriction).
        * ``cleaned_text`` is the input text with the wake word (and
          optional trailing separator) removed from wherever it appeared.
          When *matched* is ``False`` the original text is returned
          unchanged.
    """
    if not wake_word:
        # No wake word configured -- accept everything.
        return True, text

    if not text:
        return False, ""

    # Case-insensitive search for the wake word as a whole word.
    # Strips optional trailing separators: comma, colon, dash, with surrounding whitespace.
    # Handles: "Jarvis hello", "Jarvis, hello", "Jarvis - hello"
    pattern = re.compile(
        r"\b" + re.escape(wake_word) + r"\b\s*[,:\-]?\s*",
        re.IGNORECASE,
    )
    match = pattern.search(text)

    if match is None:
        return False, text

    cleaned = (text[: match.start()] + text[match.end() :]).strip()
    return True, cleaned
