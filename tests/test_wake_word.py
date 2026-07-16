"""Tests for wake word detection utility."""

from whaagent.services.wake_word import check_wake_word


class TestCheckWakeWord:
    """Tests for check_wake_word function."""

    def test_wake_word_at_start(self) -> None:
        """Wake word at start of text is detected and stripped."""
        matched, cleaned = check_wake_word("Jarvis what's the weather", "Jarvis")
        assert matched is True
        assert cleaned == "what's the weather"

    def test_wake_word_with_comma(self) -> None:
        """Wake word followed by comma separator is stripped."""
        matched, cleaned = check_wake_word("Jarvis, what's the weather", "Jarvis")
        assert matched is True
        assert cleaned == "what's the weather"

    def test_wake_word_with_colon(self) -> None:
        """Wake word followed by colon separator is stripped."""
        matched, cleaned = check_wake_word("Jarvis: set a timer", "Jarvis")
        assert matched is True
        assert cleaned == "set a timer"

    def test_wake_word_with_dash(self) -> None:
        """Wake word followed by dash separator is stripped."""
        matched, cleaned = check_wake_word("Jarvis - remind me", "Jarvis")
        assert matched is True
        assert cleaned == "remind me"

    def test_wake_word_case_insensitive(self) -> None:
        """Wake word matching is case-insensitive."""
        matched, cleaned = check_wake_word("jarvis hello", "Jarvis")
        assert matched is True
        assert cleaned == "hello"

    def test_wake_word_case_insensitive_upper(self) -> None:
        """Wake word matching works with uppercase text."""
        matched, cleaned = check_wake_word("JARVIS DO SOMETHING", "jarvis")
        assert matched is True
        assert cleaned == "DO SOMETHING"

    def test_wake_word_mid_sentence(self) -> None:
        """Wake word in middle of text is detected and stripped."""
        matched, cleaned = check_wake_word("Hey Jarvis tell me", "Jarvis")
        assert matched is True
        assert cleaned == "Hey tell me"

    def test_no_wake_word(self) -> None:
        """Text without wake word returns matched=False."""
        matched, cleaned = check_wake_word("hello there", "Jarvis")
        assert matched is False
        assert cleaned == "hello there"

    def test_no_wake_word_similar_word(self) -> None:
        """Similar but different word should not match (whole word match)."""
        matched, cleaned = check_wake_word("Jarvisson is my name", "Jarvis")
        assert matched is False
        assert cleaned == "Jarvisson is my name"

    def test_wake_word_none_accepts_all(self) -> None:
        """None wake word accepts all text."""
        matched, cleaned = check_wake_word("hello there", None)
        assert matched is True
        assert cleaned == "hello there"

    def test_wake_word_empty_string_accepts_all(self) -> None:
        """Empty string wake word accepts all text."""
        matched, cleaned = check_wake_word("hello there", "")
        assert matched is True
        assert cleaned == "hello there"

    def test_empty_text_no_match(self) -> None:
        """Empty text with wake word returns no match."""
        matched, cleaned = check_wake_word("", "Jarvis")
        assert matched is False
        assert cleaned == ""

    def test_empty_text_no_wake_word(self) -> None:
        """Empty text with no wake word returns match."""
        matched, cleaned = check_wake_word("", None)
        assert matched is True
        assert cleaned == ""

    def test_wake_word_only(self) -> None:
        """Text that is only the wake word returns match with empty cleaned text."""
        matched, cleaned = check_wake_word("Jarvis", "Jarvis")
        assert matched is True
        assert cleaned == ""

    def test_wake_word_with_trailing_whitespace(self) -> None:
        """Wake word with trailing whitespace is stripped cleanly."""
        matched, cleaned = check_wake_word("Jarvis   hello world", "Jarvis")
        assert matched is True
        assert cleaned == "hello world"

    def test_wake_word_at_end(self) -> None:
        """Wake word at end of text is detected and stripped."""
        matched, cleaned = check_wake_word("hello Jarvis", "Jarvis")
        assert matched is True
        assert cleaned == "hello"

    def test_different_wake_words(self) -> None:
        """Different wake words can be configured."""
        matched, cleaned = check_wake_word("Alice what time is it", "Alice")
        assert matched is True
        assert cleaned == "what time is it"

    def test_wake_word_not_present_different_word(self) -> None:
        """Wake word not present in text returns False."""
        matched, cleaned = check_wake_word("Alice what time is it", "Jarvis")
        assert matched is False
        assert cleaned == "Alice what time is it"
