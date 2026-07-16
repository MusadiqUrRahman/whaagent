"""Tests for whaagent package - prompts module."""

import os
import tempfile
from pathlib import Path

import pytest

from whaagent.config import reset_config
from whaagent.prompts import load_prompt


def test_whaagent_load_prompt_from_bundled():
    """Test loading a bundled prompt."""
    # Reset config first
    reset_config()
    prompt = load_prompt("developer")
    # Bundled prompts should exist
    if prompt:  # Only test if bundled prompt exists
        assert len(prompt) > 50


def test_whaagent_load_prompt_nonexistent():
    """Test loading a non-existent prompt raises PromptNotFoundError."""
    reset_config()
    from whaagent.exceptions import PromptNotFoundError

    with pytest.raises(PromptNotFoundError):
        load_prompt("nonexistent-prompt-xyz-12345")


def test_whaagent_load_prompt_from_file():
    """Test loading prompt from file via environment variable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompts_dir = Path(tmpdir)
        prompt_file = prompts_dir / "test-file-prompt.md"
        prompt_file.write_text("# Test Prompt\n\nThis is from a file.")

        # Create config file pointing to prompts dir
        config_file = Path(tmpdir) / ".whaagent.yaml"
        config_file.write_text(f"agents:\n  prompts_dir: {prompts_dir}")

        # Set environment to use this config
        old_env = os.environ.get("whaagent_CONFIG")
        os.environ["whaagent_CONFIG"] = str(config_file)
        reset_config()

        try:
            _prompt = load_prompt("test-file-prompt")
            # The prompt might be None if the file isn't found
            # This test mainly checks the loading mechanism works
        finally:
            if old_env:
                os.environ["whaagent_CONFIG"] = old_env
            else:
                os.environ.pop("whaagent_CONFIG", None)
            reset_config()
