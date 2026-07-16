"""Tests for whaagent package - codebase explorer tools module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from whaagent.tools.codebase_explorer import (
    CodebaseExplorer,
    FileEditorTool,
    FileFinderTool,
    FileFragmentReaderTool,
    FileOutlinerTool,
    StructureExplorerTool,
)


class TestCodebaseExplorer:
    """Test CodebaseExplorer base class."""

    def test_codebase_explorer_initialization(self):
        """Test CodebaseExplorer initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            explorer = CodebaseExplorer(root_dir=tmpdir)
            assert explorer.root_dir == Path(tmpdir).resolve()

    def test_codebase_explorer_default_ignore_patterns(self):
        """Test CodebaseExplorer has default ignore patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            explorer = CodebaseExplorer(root_dir=tmpdir)
            assert ".git" in explorer.ignore_patterns
            assert "__pycache__" in explorer.ignore_patterns
            assert "node_modules" in explorer.ignore_patterns

    def test_codebase_explorer_custom_ignore_patterns(self):
        """Test CodebaseExplorer with custom ignore patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_patterns = ["custom_dir", "*.tmp"]
            explorer = CodebaseExplorer(root_dir=tmpdir, ignore_patterns=custom_patterns)
            assert explorer.ignore_patterns == custom_patterns

    def test_codebase_explorer_is_ignored(self):
        """Test _is_ignored method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            explorer = CodebaseExplorer(root_dir=tmpdir)

            # Create ignored path
            git_dir = Path(tmpdir) / ".git"
            assert explorer._is_ignored(git_dir) is True

            # Create non-ignored path
            src_dir = Path(tmpdir) / "src"
            assert explorer._is_ignored(src_dir) is False


class TestStructureExplorerTool:
    """Test StructureExplorerTool."""

    def test_structure_explorer_name(self):
        """Test StructureExplorerTool has correct name."""
        tool = StructureExplorerTool(root_dir="/tmp")
        assert tool.name == "discover_structure"

    def test_structure_explorer_description(self):
        """Test StructureExplorerTool has description."""
        tool = StructureExplorerTool(root_dir="/tmp")
        assert tool.description is not None
        assert len(tool.description) > 0

    def test_structure_explorer_build_tree_default_depth(self):
        """Test structure explorer with default depth."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directory structure
            (Path(tmpdir) / "dir1").mkdir()
            (Path(tmpdir) / "dir2").mkdir()
            (Path(tmpdir) / "file1.txt").write_text("content")
            (Path(tmpdir) / "dir1" / "file2.txt").write_text("content")

            tool = StructureExplorerTool(root_dir=tmpdir)
            result = tool.invoke("")  # Uses default depth 3

            assert result["name"] == Path(tmpdir).name
            assert result["type"] == "directory"
            assert len(result["children"]) >= 3

    def test_structure_explorer_max_depth(self):
        """Test structure explorer with max depth limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            (Path(tmpdir) / "a" / "b" / "c" / "d").mkdir(parents=True)

            tool = StructureExplorerTool(root_dir=tmpdir)
            result = tool.invoke("1")  # Limit to depth 1

            # Should only show top level
            assert len(result["children"]) == 1
            assert result["children"][0]["name"] == "a"

    def test_structure_explorer_ignored_paths(self):
        """Test structure explorer ignores configured paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directories
            (Path(tmpdir) / ".git").mkdir()
            (Path(tmpdir) / "src").mkdir()
            (Path(tmpdir) / "node_modules").mkdir()

            tool = StructureExplorerTool(root_dir=tmpdir)
            result = tool.invoke("")

            # Should not include .git and node_modules
            child_names = [c["name"] for c in result["children"]]
            assert "src" in child_names
            assert ".git" not in child_names
            assert "node_modules" not in child_names

    def test_structure_explorer_permission_denied(self):
        """Test structure explorer handles permission errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = StructureExplorerTool(root_dir=tmpdir)

            # Create a file and make it unreadable (simulated)
            restricted_dir = Path(tmpdir) / "restricted"
            restricted_dir.mkdir()

            # Create structure that may hit permission issues
            result = tool.invoke("")

            # Should return structure without crashing
            assert result["type"] == "directory"


class TestFileOutlinerTool:
    """Test FileOutlinerTool."""

    def test_file_outliner_name(self):
        """Test FileOutlinerTool has correct name."""
        tool = FileOutlinerTool(root_dir="/tmp")
        assert tool.name == "get_file_outline"

    def test_file_outliner_description(self):
        """Test FileOutlinerTool has description."""
        tool = FileOutlinerTool(root_dir="/tmp")
        assert tool.description is not None

    def test_file_outliner_detect_language(self):
        """Test language detection from file extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileOutlinerTool(root_dir=tmpdir)

            # Test various extensions
            assert tool._detect_language("test.py") == "python"
            assert tool._detect_language("test.js") == "javascript"
            assert tool._detect_language("test.ts") == "typescript"
            assert tool._detect_language("test.rs") == "rust"
            assert tool._detect_language("test.go") == "go"
            assert tool._detect_language("test.java") == "java"
            assert tool._detect_language("test.c") == "c"
            assert tool._detect_language("test.cpp") == "cpp"
            assert tool._detect_language("test.php") == "php"
            assert tool._detect_language("test.xyz") is None

    def test_file_outliner_python(self):
        """Test extracting outline from Python file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test Python file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
class MyClass:
    def method1(self):
        pass

    async def method2(self):
        pass

def function1():
    pass
""")

            tool = FileOutlinerTool(root_dir=tmpdir)
            result = tool.invoke("test.py")

            assert isinstance(result, list)
            assert len(result) >= 3
            signatures = [item["signature"] for item in result]
            assert any("class MyClass" in s for s in signatures)
            assert any("def method1" in s for s in signatures)
            assert any("def function1" in s for s in signatures)

    def test_file_outliner_file_not_found(self):
        """Test FileOutlinerTool with missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileOutlinerTool(root_dir=tmpdir)
            result = tool.invoke("nonexistent.py")

            assert "Error: File nonexistent.py not found" in result

    def test_file_outliner_unsupported_type(self):
        """Test FileOutlinerTool with unsupported file type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create unsupported file
            test_file = Path(tmpdir) / "test.xyz"
            test_file.write_text("content")

            tool = FileOutlinerTool(root_dir=tmpdir)
            result = tool.invoke("test.xyz")

            assert "Error: Unsupported file type" in result


class TestFileFragmentReaderTool:
    """Test FileFragmentReaderTool."""

    def test_file_fragment_reader_name(self):
        """Test FileFragmentReaderTool has correct name."""
        tool = FileFragmentReaderTool(root_dir="/tmp")
        assert tool.name == "read_file_fragment"

    def test_file_fragment_reader_valid_range(self):
        """Test reading valid line range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            content = "line1\nline2\nline3\nline4\nline5\n"
            test_file.write_text(content)

            tool = FileFragmentReaderTool(root_dir=tmpdir)
            result = tool.invoke("test.txt:2:4")

            assert "line2" in result
            assert "line3" in result
            assert "line4" in result

    def test_file_fragment_reader_invalid_format(self):
        """Test FileFragmentReaderTool with invalid format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileFragmentReaderTool(root_dir=tmpdir)
            result = tool.invoke("test.txt")

            assert "Error: Invalid input format" in result

    def test_file_fragment_reader_file_not_found(self):
        """Test FileFragmentReaderTool with missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileFragmentReaderTool(root_dir=tmpdir)
            result = tool.invoke("nonexistent.txt:1:10")

            assert "Error: File nonexistent.txt not found" in result

    def test_file_fragment_reader_out_of_bounds(self):
        """Test FileFragmentReaderTool with out of bounds range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\n")

            tool = FileFragmentReaderTool(root_dir=tmpdir)
            # Should handle gracefully
            result = tool.invoke("test.txt:100:200")
            assert isinstance(result, str)


class TestFileFinderTool:
    """Test FileFinderTool."""

    def test_file_finder_name(self):
        """Test FileFinderTool has correct name."""
        tool = FileFinderTool(root_dir="/tmp")
        assert tool.name == "find_files"

    def test_file_finder_description(self):
        """Test FileFinderTool has description."""
        tool = FileFinderTool(root_dir="/tmp")
        assert tool.description is not None

    def test_file_finder_fallback_matching(self):
        """Test FileFinderTool with fallback matching when fzf unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "test1.py").write_text("content")
            (Path(tmpdir) / "test2.py").write_text("content")
            (Path(tmpdir) / "other.txt").write_text("content")

            tool = FileFinderTool(root_dir=tmpdir)

            with patch("whaagent.tools.codebase_explorer.subprocess.run") as mock_run:
                # Mock fd to return files, then simulate fzf failure
                fd_result = MagicMock(stdout="test1.py\ntest2.py\nother.txt\n", returncode=0)
                fzf_result = MagicMock(returncode=1, stdout="")  # fzf fails
                mock_run.side_effect = [fd_result, fzf_result]

                result = tool.invoke("test")

                # Should fall back to substring matching
                assert "test1.py" in result
                assert "test2.py" in result

    def test_file_finder_no_matches(self):
        """Test FileFinderTool with no matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileFinderTool(root_dir=tmpdir)

            with patch("whaagent.tools.codebase_explorer.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)

                result = tool.invoke("nonexistent")

                assert "No matches found" in result

    def test_file_finder_fd_error(self):
        """Test FileFinderTool when fd fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileFinderTool(root_dir=tmpdir)

            with patch("whaagent.tools.codebase_explorer.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="fd error")

                result = tool.invoke("test")

                assert "Error" in result


class TestFileEditorTool:
    """Test FileEditorTool."""

    def test_file_editor_name(self):
        """Test FileEditorTool has correct name."""
        tool = FileEditorTool(root_dir="/tmp")
        assert tool.name == "edit_file"

    def test_file_editor_description(self):
        """Test FileEditorTool has description."""
        tool = FileEditorTool(root_dir="/tmp")
        assert tool.description is not None

    def test_file_editor_replace_lines(self):
        """Test replacing lines in a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

            tool = FileEditorTool(root_dir=tmpdir)
            result = tool.invoke("replace:test.txt:2:3:REPLACED")

            assert "Replaced lines 2-3" in result

            # Verify content
            content = test_file.read_text()
            assert "line1\nREPLACED\nline4\nline5" in content

    def test_file_editor_replace_json(self):
        """Test replacing lines using JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\n")

            tool = FileEditorTool(root_dir=tmpdir)

            input_json = json.dumps({"op": "replace", "path": "test.txt", "start": 2, "end": 2, "content": "REPLACED"})

            result = tool.invoke(input_json)
            assert "Replaced lines 2-2" in result

            content = test_file.read_text()
            assert "line1\nREPLACED\nline3" in content

    def test_file_editor_insert_after(self):
        """Test inserting content after a line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\n")

            tool = FileEditorTool(root_dir=tmpdir)
            result = tool.invoke("insert:test.txt:2:INSERTED")

            assert "after line 2" in result

            content = test_file.read_text()
            assert "line1\nline2\nINSERTED\nline3" in content

    def test_file_editor_insert_before(self):
        """Test inserting content before a line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\n")

            tool = FileEditorTool(root_dir=tmpdir)
            result = tool.invoke("insert:test.txt:before_2:INSERTED")

            assert "before line 2" in result

            content = test_file.read_text()
            assert "line1\nINSERTED\nline2\nline3" in content

    def test_file_editor_delete_lines(self):
        """Test deleting lines from a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

            tool = FileEditorTool(root_dir=tmpdir)
            result = tool.invoke("delete:test.txt:2:3")

            assert "Deleted 2 line(s)" in result

            content = test_file.read_text()
            assert "line1\nline4\nline5" in content

    def test_file_editor_search_replace(self):
        """Test search and replace operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nTARGET_LINE\nline3\n")

            tool = FileEditorTool(root_dir=tmpdir)

            input_json = json.dumps(
                {"op": "search_replace", "path": "test.txt", "old": "TARGET_LINE", "new": "REPLACED"}
            )

            result = tool.invoke(input_json)
            assert "Replaced text at lines" in result

            content = test_file.read_text()
            assert "TARGET_LINE" not in content
            assert "REPLACED" in content

    def test_file_editor_search_replace_not_found(self):
        """Test search and replace with text not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\n")

            tool = FileEditorTool(root_dir=tmpdir)

            input_json = json.dumps({"op": "search_replace", "path": "test.txt", "old": "NOT_FOUND", "new": "REPLACED"})

            result = tool.invoke(input_json)
            assert "Error: Search text not found" in result

    def test_file_editor_search_replace_multiple_matches(self):
        """Test search and replace with multiple matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nTARGET\nline3\nTARGET\n")

            tool = FileEditorTool(root_dir=tmpdir)

            input_json = json.dumps({"op": "search_replace", "path": "test.txt", "old": "TARGET", "new": "REPLACED"})

            result = tool.invoke(input_json)
            assert "Found 2 occurrences" in result

    def test_file_editor_path_validation_traversal(self):
        """Test FileEditorTool rejects path traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileEditorTool(root_dir=tmpdir)

            # Attempt to edit file outside root
            with pytest.raises(ValueError) as exc_info:
                tool._validate_path("../etc/passwd")

            assert "outside of project root" in str(exc_info.value)

    def test_file_editor_binary_rejection(self):
        """Test FileEditorTool rejects binary files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileEditorTool(root_dir=tmpdir)

            # Attempt to edit binary file
            with pytest.raises(ValueError) as exc_info:
                tool._validate_path("test.exe")

            assert "Cannot edit binary file" in str(exc_info.value)

    def test_file_editor_invalid_line_bounds(self):
        """Test FileEditorTool validates line bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileEditorTool(root_dir=tmpdir)

            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\n")

            # Invalid: start < 1
            with pytest.raises(ValueError) as exc_info:
                tool._validate_line_bounds(["line1\nline2\nline3"], 0, 2, "test.txt")
            assert "Start line must be >= 1" in str(exc_info.value)

            # Invalid: end < start
            with pytest.raises(ValueError) as exc_info:
                tool._validate_line_bounds(["line1\nline2\nline3"], 3, 2, "test.txt")
            assert "End line (2) must be >= start line (3)" in str(exc_info.value)

    def test_file_editor_large_file_warning(self):
        """Test FileEditorTool warns for large files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileEditorTool(root_dir=tmpdir)

            # Create file just above warning threshold
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("x" * (FileEditorTool.WARN_FILE_SIZE + 100))

            warning = tool._check_file_size(test_file)
            assert warning is not None
            assert "Warning: Large file" in warning

    def test_file_editor_too_large_error(self):
        """Test FileEditorTool rejects files over maximum size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileEditorTool(root_dir=tmpdir)

            # Create file over maximum size
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("x" * (FileEditorTool.MAX_FILE_SIZE + 100))

            with pytest.raises(ValueError) as exc_info:
                tool._check_file_size(test_file)
            assert "File too large" in str(exc_info.value)

    def test_file_editor_unknown_operation(self):
        """Test FileEditorTool with unknown operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileEditorTool(root_dir=tmpdir)

            input_json = json.dumps({"op": "unknown", "path": "test.txt"})

            result = tool.invoke(input_json)
            assert "Error: Unknown operation 'unknown'" in result
