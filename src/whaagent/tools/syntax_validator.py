"""Syntax validation module using Tree-sitter for multi-language support."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from tree_sitter import Parser

# Language detection by file extension
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".php": "php",
}

# Map our language names to tree-sitter-languages names
TREE_SITTER_LANGUAGE_MAP: Dict[str, str] = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "rust": "rust",
    "go": "go",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "php": "php",
}

# Maximum file size to validate (for performance)
MAX_FILE_SIZE = 500 * 1024  # 500KB


@dataclass
class ValidationError:
    """Represents a single syntax error."""

    line: int
    column: int
    message: str

    def __str__(self) -> str:
        return f"Line {self.line}, Col {self.column}: {self.message}"


@dataclass
class ValidationResult:
    """Result of syntax validation."""

    is_valid: bool
    language: Optional[str]
    errors: list[ValidationError]
    skipped: bool = False
    skip_reason: Optional[str] = None

    @property
    def warning_message(self) -> Optional[str]:
        """Generate a warning message if there are errors."""
        if self.is_valid or self.skipped:
            return None

        error_count = len(self.errors)
        lang_str = self.language or "unknown"

        lines = ["\n\nSYNTAX WARNING:", f"Found {error_count} syntax error(s) in {lang_str} code:"]

        for error in self.errors[:5]:  # Limit to first 5 errors
            lines.append(f"  {error}")

        if error_count > 5:
            lines.append(f"  ... and {error_count - 5} more error(s)")

        return "\n".join(lines)


class SyntaxValidator:
    """Validates syntax of code files using Tree-sitter."""

    def __init__(self) -> None:
        self._parsers: Dict[str, "Parser"] = {}
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if tree-sitter is available."""
        import importlib.util

        return importlib.util.find_spec("tree_sitter_languages") is not None

    def _get_parser(self, language: str) -> Optional["Parser"]:
        """Get or create a parser for given language."""
        if not self._available:
            return None

        ts_lang = TREE_SITTER_LANGUAGE_MAP.get(language)
        if not ts_lang:
            return None

        if ts_lang not in self._parsers:
            try:
                import tree_sitter_languages  # type: ignore[import-untyped]

                parser = tree_sitter_languages.get_parser(ts_lang)
                self._parsers[ts_lang] = parser
            except Exception:
                return None

        return self._parsers[ts_lang]

    def validate(self, content: str, file_path: str) -> ValidationResult:
        """Validate the syntax of given content.

        Args:
            content: The source code content to validate
            file_path: Path to the file (used for language detection)

        Returns:
            ValidationResult with validity status and any errors
        """
        # Detect language from file extension
        ext = Path(file_path).suffix.lower()
        language = LANGUAGE_EXTENSIONS.get(ext)

        if language is None:
            return ValidationResult(
                is_valid=True,
                language=None,
                errors=[],
                skipped=True,
                skip_reason=f"Unsupported file extension: {ext}",
            )

        # Check file size
        content_size = len(content.encode("utf-8"))
        if content_size > MAX_FILE_SIZE:
            return ValidationResult(
                is_valid=True,
                language=language,
                errors=[],
                skipped=True,
                skip_reason=f"File too large ({content_size} bytes)",
            )

        # Check if tree-sitter is available
        if not self._available:
            return ValidationResult(
                is_valid=True,
                language=language,
                errors=[],
                skipped=True,
                skip_reason="tree-sitter-languages not installed",
            )

        # Get parser for language
        parser = self._get_parser(language)
        if parser is None:
            return ValidationResult(
                is_valid=True,
                language=language,
                errors=[],
                skipped=True,
                skip_reason=f"No parser available for {language}",
            )

        # Parse content
        try:
            tree = parser.parse(content.encode("utf-8"))
        except Exception as e:
            return ValidationResult(
                is_valid=True,
                language=language,
                errors=[],
                skipped=True,
                skip_reason=f"Parse error: {e}",
            )

        # Find errors in tree
        errors = self._find_errors(tree.root_node)

        return ValidationResult(
            is_valid=len(errors) == 0,
            language=language,
            errors=errors,
            skipped=False,
            skip_reason=None,
        )

    def _find_errors(self, node: Any) -> list[ValidationError]:
        """Recursively find ERROR nodes in AST."""
        errors: list[ValidationError] = []

        if hasattr(node, "type") and node.type == "ERROR":
            # Get location of error
            start_point = node.start_point
            errors.append(
                ValidationError(
                    line=start_point[0] + 1,  # 0-indexed to 1-indexed
                    column=start_point[1] + 1,
                    message=f"Syntax error near '{self._get_error_context(node)}'",
                )
            )

        # Recursively check children
        if hasattr(node, "children"):
            for child in node.children:
                errors.extend(self._find_errors(child))

        return errors

    def _get_error_context(self, node: Any) -> str:
        """Get a short context string for an error node."""
        try:
            if hasattr(node, "text"):
                text = node.text.decode("utf-8") if isinstance(node.text, bytes) else str(node.text)
                # Limit to 30 chars for readability
                if len(text) > 30:
                    return text[:27] + "..."
                return text or "<empty>"
        except Exception:
            pass
        return "<unknown>"


# Singleton instance
_validator: Optional[SyntaxValidator] = None


def get_validator() -> SyntaxValidator:
    """Get the singleton SyntaxValidator instance."""
    global _validator
    if _validator is None:
        _validator = SyntaxValidator()
    return _validator
