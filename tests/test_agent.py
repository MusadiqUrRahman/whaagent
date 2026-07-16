"""Tests for AgentBase model resolution from config."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


class TestAgentModelResolution:
    """Tests for per-agent model resolution in AgentBase.__init__."""

    def test_uses_agent_model_from_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Agent should use model from agent_models config when set."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {"model": "global-default-model"},
                    "agent_models": {"developer": "glm-5"},
                }
            )
        )
        monkeypatch.setenv("whaagent_CONFIG", str(config_file))

        with patch("whaagent.agent._create_model") as mock_create:
            mock_create.return_value = MagicMock()
            from whaagent.agent import AgentBase
            from whaagent.config import get_config

            get_config(force_reload=True)

            class TestAgent(AgentBase):
                @property
                def system_prompt(self) -> str:
                    return "test"

            TestAgent(_agent_name="developer")
            mock_create.assert_called_once_with("glm-5", 0.1)

    def test_falls_back_to_global_model(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Agent should fall back to llm.model when not in agent_models."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {"model": "global-default-model"},
                    "agent_models": {"assistant": "glm-5.1"},
                }
            )
        )
        monkeypatch.setenv("whaagent_CONFIG", str(config_file))

        with patch("whaagent.agent._create_model") as mock_create:
            mock_create.return_value = MagicMock()
            from whaagent.agent import AgentBase
            from whaagent.config import get_config

            get_config(force_reload=True)

            class TestAgent(AgentBase):
                @property
                def system_prompt(self) -> str:
                    return "test"

            # "developer" is not in agent_models, should use global default
            TestAgent(_agent_name="developer")
            mock_create.assert_called_once_with("global-default-model", 0.1)

    def test_explicit_model_name_overrides_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit model_name parameter should override config."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump({"llm": {"model": "global-default"}, "agent_models": {"assistant": "glm-5.1"}})
        )
        monkeypatch.setenv("whaagent_CONFIG", str(config_file))

        with patch("whaagent.agent._create_model") as mock_create:
            mock_create.return_value = MagicMock()
            from whaagent.agent import AgentBase
            from whaagent.config import get_config

            get_config(force_reload=True)

            class TestAgent(AgentBase):
                @property
                def system_prompt(self) -> str:
                    return "test"

            TestAgent(model_name="explicit-model", _agent_name="assistant")
            mock_create.assert_called_once_with("explicit-model", 0.1)

    def test_no_config_falls_back_to_provider_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without config, should fall back to provider default."""
        monkeypatch.setenv("whaagent_CONFIG", "__nonexistent__")

        with patch("whaagent.agent._create_model") as mock_create:
            mock_create.return_value = MagicMock()
            with patch("whaagent.agent.get_default_model", return_value="provider-default"):
                from whaagent.agent import AgentBase
                from whaagent.config import get_config

                get_config(force_reload=True)

                class TestAgent(AgentBase):
                    @property
                    def system_prompt(self) -> str:
                        return "test"

                TestAgent(_agent_name="unknown-agent")
                mock_create.assert_called_once_with("provider-default", 0.1)


class TestGetNodeModels:
    """Tests for _get_node_models helper on AgentBase."""

    def test_returns_configured_node_models(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return model instances for nodes with overrides."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {"model": "glm-4.7", "temperature": 0.1},
                    "agent_models": {
                        "assistant": "glm-5.1",
                        "assistant_nodes": {
                            "router": "glm-4.7",
                            "agent": "glm-4.7",
                        },
                    },
                }
            )
        )
        monkeypatch.setenv("whaagent_CONFIG", str(config_file))

        with patch("whaagent.agent._create_model") as mock_create:
            mock_create.return_value = MagicMock()
            from whaagent.agent import AgentBase
            from whaagent.config import get_config

            get_config(force_reload=True)

            class TestAgent(AgentBase):
                @property
                def system_prompt(self) -> str:
                    return "test"

            agent = TestAgent(_agent_name="assistant")
            node_models = agent._get_node_models()

            # Should have router and agent (from config)
            assert "router" in node_models
            assert "agent" in node_models

    def test_returns_empty_when_no_overrides(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return empty dict when no node overrides configured."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(yaml.dump({"llm": {"model": "glm-4.7"}, "agent_models": {"developer": "glm-5"}}))
        monkeypatch.setenv("whaagent_CONFIG", str(config_file))

        with patch("whaagent.agent._create_model") as mock_create:
            mock_create.return_value = MagicMock()
            from whaagent.agent import AgentBase
            from whaagent.config import get_config

            get_config(force_reload=True)

            class TestAgent(AgentBase):
                @property
                def system_prompt(self) -> str:
                    return "test"

            agent = TestAgent(_agent_name="developer")
            node_models = agent._get_node_models()
            assert node_models == {}
