"""Tests for whaagent init command."""

from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from whaagent.cli import app

runner = CliRunner()


class TestInitCommand:
    """Tests for the 'whaagent init' command."""

    def test_init_creates_config_with_z_ai(self, tmp_path: Path) -> None:
        """Init with z.ai provider creates config with openai provider + base URL."""
        config_file = tmp_path / ".whaagent.yaml"
        env_file = tmp_path / ".env"
        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch("whaagent.cli_init._get_env_path", return_value=env_file),
            patch(
                "rich.prompt.Prompt.ask",
                side_effect=[
                    "z.ai",  # provider
                    "glm-4.7",  # model
                    "0.1",  # temperature
                    "sk-z-api-key",  # api key
                    "https://api.z.ai/api/coding/paas/v4",  # base url (default)
                ],
            ),
            patch("rich.prompt.Confirm.ask", side_effect=[True, False]),  # write env, no whatsapp
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output
        assert config_file.exists()

        with config_file.open() as f:
            config = yaml.safe_load(f)

        # z.ai maps to "openai" provider internally
        assert config["llm"]["provider"] == "openai"
        assert config["llm"]["model"] == "glm-4.7"
        assert config["llm"]["temperature"] == 0.1

        # .env should have both API key and base URL
        assert env_file.exists()
        content = env_file.read_text()
        assert "OPENAI_API_KEY=sk-z-api-key" in content
        assert "OPENAI_BASE_URL=https://api.z.ai/api/coding/paas/v4" in content

    def test_init_creates_config_file_with_anthropic(self, tmp_path: Path) -> None:
        """Init with Anthropic provider creates valid ~/.whaagent.yaml."""
        config_file = tmp_path / ".whaagent.yaml"
        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch(
                "rich.prompt.Prompt.ask",
                side_effect=["anthropic", "claude-sonnet-4-6", "0.1", "sk-ant-test-key"],
            ),
            patch("rich.prompt.Confirm.ask", side_effect=[True, False]),  # write env, no whatsapp
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output
        assert config_file.exists()

        with config_file.open() as f:
            config = yaml.safe_load(f)

        assert config["llm"]["provider"] == "anthropic"
        assert config["llm"]["model"] == "claude-sonnet-4-6"
        assert config["llm"]["temperature"] == 0.1

    def test_init_creates_config_file_with_openai(self, tmp_path: Path) -> None:
        """Init with OpenAI provider creates valid config (no base URL needed)."""
        config_file = tmp_path / ".whaagent.yaml"
        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch(
                "rich.prompt.Prompt.ask",
                side_effect=["openai", "gpt-4o-mini", "0.3", "sk-openai-key"],
            ),
            patch("rich.prompt.Confirm.ask", side_effect=[True, False]),  # write env, no whatsapp
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output

        with config_file.open() as f:
            config = yaml.safe_load(f)

        assert config["llm"]["provider"] == "openai"
        assert config["llm"]["model"] == "gpt-4o-mini"

    def test_init_with_ollama_no_api_key_needed(self, tmp_path: Path) -> None:
        """Init with Ollama provider skips API key, prompts for base URL."""
        config_file = tmp_path / ".whaagent.yaml"
        env_file = tmp_path / ".env"
        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch("whaagent.cli_init._get_env_path", return_value=env_file),
            patch(
                "rich.prompt.Prompt.ask",
                side_effect=["ollama", "llama3", "0.7", "http://localhost:11434"],
            ),
            patch("rich.prompt.Confirm.ask", side_effect=[True, False]),  # write env, no whatsapp
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output

        with config_file.open() as f:
            config = yaml.safe_load(f)

        assert config["llm"]["provider"] == "ollama"
        assert config["llm"]["model"] == "llama3"

        # .env should have OLLAMA_BASE_URL but no API key
        content = env_file.read_text()
        assert "OLLAMA_BASE_URL=http://localhost:11434" in content

    def test_init_rejects_invalid_provider(self, tmp_path: Path) -> None:
        """Init rejects an unsupported provider and asks again."""
        config_file = tmp_path / ".whaagent.yaml"
        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch(
                "rich.prompt.Prompt.ask",
                side_effect=["invalid_provider", "openai", "gpt-4o-mini", "0.3", "sk-test"],
            ),
            patch("rich.prompt.Confirm.ask", side_effect=[True, False]),  # write env, no whatsapp
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output

        with config_file.open() as f:
            config = yaml.safe_load(f)

        assert config["llm"]["provider"] == "openai"

    def test_init_skips_if_config_exists_and_user_declines(self, tmp_path: Path) -> None:
        """Init aborts when config file exists and user says no to overwrite."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text("llm:\n  provider: openai\n")

        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output
        assert "Aborted" in result.output or "skipped" in result.output.lower()

    def test_init_overwrites_when_user_confirms(self, tmp_path: Path) -> None:
        """Init overwrites existing config when user confirms."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text("llm:\n  provider: openai\n")

        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch(
                "rich.prompt.Prompt.ask",
                side_effect=["anthropic", "claude-sonnet-4-6", "0.1", "sk-ant-test-key"],
            ),
            patch("rich.prompt.Confirm.ask", side_effect=[True, True, False]),  # overwrite, write env, no whatsapp
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output

        with config_file.open() as f:
            config = yaml.safe_load(f)

        assert config["llm"]["provider"] == "anthropic"

    def test_init_with_whatsapp_tenant(self, tmp_path: Path) -> None:
        """Init with WhatsApp setup writes tenant config."""
        config_file = tmp_path / ".whaagent.yaml"
        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch(
                "rich.prompt.Prompt.ask",
                side_effect=[
                    "openai",  # provider
                    "gpt-4o-mini",  # model
                    "0.3",  # temperature
                    "sk-openai-key",  # api key
                    "personal",  # tenant id
                    "+5511999999999",  # phone
                    "assistant",  # default agent
                ],
            ),
            patch("rich.prompt.Confirm.ask", side_effect=[True, True]),
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output

        with config_file.open() as f:
            config = yaml.safe_load(f)

        assert config["whatsapp"]["tenants"][0]["id"] == "personal"
        assert config["whatsapp"]["tenants"][0]["phone"] == "+5511999999999"
        assert config["whatsapp"]["tenants"][0]["default_agent"] == "assistant"

    def test_init_without_whatsapp_tenant(self, tmp_path: Path) -> None:
        """Init without WhatsApp omits whatsapp section from config."""
        config_file = tmp_path / ".whaagent.yaml"
        with (
            patch("whaagent.cli_init._get_config_path", return_value=config_file),
            patch(
                "rich.prompt.Prompt.ask",
                side_effect=["openai", "gpt-4o-mini", "0.3", "sk-key"],
            ),
            patch("rich.prompt.Confirm.ask", side_effect=[True, False]),
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output

        with config_file.open() as f:
            config = yaml.safe_load(f)

        assert "whatsapp" not in config
