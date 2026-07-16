"""Tests for unified configuration."""

from pathlib import Path

import pytest
import yaml


class TestUnifiedConfig:
    """Tests for unified configuration loading."""

    def test_config_loads_all_sections(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config should load all required sections."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {"provider": "openai", "model": "gpt-4", "temperature": 0.5},
                    "api": {"host": "0.0.0.0", "port": 9000},
                    "storage": {"base_path": str(tmp_path / "data")},
                    "auth": {"api_keys": {"test-key": "tenant-1"}},
                }
            )
        )

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        assert config.llm.provider == "openai"
        assert config.llm.temperature == 0.5
        assert config.api.port == 9000
        assert "test-key" in config.auth.api_keys

    def test_config_loads_whatsapp_tenants(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config should load WhatsApp tenant configurations."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "whatsapp": {
                        "tenants": [
                            {"id": "personal", "phone": "+34611111111", "default_agent": "developer"},
                            {"id": "work", "phone": "+34622222222", "default_agent": "chef"},
                        ]
                    }
                }
            )
        )

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        assert len(config.whatsapp.tenants) == 2
        assert config.whatsapp.tenants[0].id == "personal"
        assert config.whatsapp.tenants[0].phone == "+34611111111"

    def test_config_get_tenant_by_phone(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_tenant_by_phone should return correct tenant."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "whatsapp": {
                        "tenants": [
                            {"id": "personal", "phone": "+34611111111"},
                        ]
                    }
                }
            )
        )

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        tenant = config.whatsapp.get_tenant_by_phone("+34611111111")
        assert tenant is not None
        assert tenant.id == "personal"

        assert config.whatsapp.get_tenant_by_phone("+99999999999") is None

    def test_config_get_tenant_db_path_sanitizes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_tenant_db_path should sanitize tenant IDs."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(yaml.dump({"storage": {"base_path": str(tmp_path / "data")}}))

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        path = config.storage.get_tenant_db_path("../../../etc/passwd")
        assert ".." not in str(path)
        assert "passwd" in str(path)  # Only alphanumeric chars kept

    def test_config_missing_sections_get_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing sections should get sensible defaults."""
        monkeypatch.setenv("whaagent_CONFIG", "__nonexistent__")
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        assert config.api.host == "127.0.0.1"
        assert config.api.port == 8000
        assert config.auth.api_keys == {}
        assert config.whatsapp.tenants == []


class TestAgentModelConfig:
    """Tests for per-agent model configuration."""

    def test_get_model_for_agent_default(self) -> None:
        """Should return model name when agent is configured."""
        from whaagent.config import AgentModelConfig

        config = AgentModelConfig(models={"assistant": "glm-5.1", "committer": "glm-4.7"})
        assert config.get_model_for("assistant") == "glm-5.1"
        assert config.get_model_for("committer") == "glm-4.7"

    def test_get_model_for_unknown_agent_returns_none(self) -> None:
        """Should return None when agent is not configured."""
        from whaagent.config import AgentModelConfig

        config = AgentModelConfig(models={"assistant": "glm-5.1"})
        assert config.get_model_for("developer") is None

    def test_get_model_for_node_override(self) -> None:
        """Should return node-specific model when configured."""
        from whaagent.config import AgentModelConfig

        config = AgentModelConfig(
            models={"assistant": "glm-5.1"},
            node_overrides={"assistant": {"router": "glm-4.7", "responder": "glm-4.7"}},
        )
        assert config.get_model_for("assistant", node="router") == "glm-4.7"
        assert config.get_model_for("assistant", node="responder") == "glm-4.7"

    def test_get_model_for_node_falls_back_to_agent_default(self) -> None:
        """Should fall back to agent default when node is not overridden."""
        from whaagent.config import AgentModelConfig

        config = AgentModelConfig(
            models={"assistant": "glm-5.1"},
            node_overrides={"assistant": {"router": "glm-4.7"}},
        )
        # executor is not in node_overrides, should fall back to agent default
        assert config.get_model_for("assistant", node="executor") == "glm-5.1"

    def test_get_model_for_node_none_returns_agent_default(self) -> None:
        """Should return agent default when node is None."""
        from whaagent.config import AgentModelConfig

        config = AgentModelConfig(
            models={"assistant": "glm-5.1"},
            node_overrides={"assistant": {"router": "glm-4.7"}},
        )
        assert config.get_model_for("assistant", node=None) == "glm-5.1"

    def test_empty_config_returns_none(self) -> None:
        """Empty config should return None for all lookups."""
        from whaagent.config import AgentModelConfig

        config = AgentModelConfig()
        assert config.get_model_for("assistant") is None
        assert config.get_model_for("assistant", node="router") is None

    def test_config_from_dict_parses_agent_models(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config should parse agent_models section from YAML."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {"model": "glm-4.7"},
                    "agent_models": {
                        "assistant": "glm-5.1",
                        "developer": "glm-5",
                        "committer": "glm-4.7",
                        "assistant_nodes": {
                            "router": "glm-4.7",
                            "executor": "glm-5.1",
                            "responder": "glm-4.7",
                        },
                    },
                }
            )
        )

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        assert config.agent_models.get_model_for("assistant") == "glm-5.1"
        assert config.agent_models.get_model_for("developer") == "glm-5"
        assert config.agent_models.get_model_for("committer") == "glm-4.7"
        assert config.agent_models.get_model_for("assistant", node="router") == "glm-4.7"
        assert config.agent_models.get_model_for("assistant", node="executor") == "glm-5.1"
        assert config.agent_models.get_model_for("assistant", node="responder") == "glm-4.7"

    def test_config_from_dict_without_agent_models(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config without agent_models should have empty AgentModelConfig."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(yaml.dump({"llm": {"model": "gpt-4"}}))

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        assert config.agent_models.get_model_for("assistant") is None
        assert config.agent_models.models == {}
        assert config.agent_models.node_overrides == {}


class TestWakeWordConfig:
    """Tests for wake_word configuration."""

    def test_wake_word_parsed_from_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config should parse wake_word from tenant YAML."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "whatsapp": {
                        "tenants": [
                            {
                                "id": "personal",
                                "phone": "+34611111111",
                                "default_agent": "assistant",
                                "wake_word": "Jarvis",
                            },
                        ]
                    }
                }
            )
        )

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        assert len(config.whatsapp.tenants) == 1
        assert config.whatsapp.tenants[0].wake_word == "Jarvis"

    def test_wake_word_default_is_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tenant without wake_word should default to None."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "whatsapp": {
                        "tenants": [
                            {
                                "id": "personal",
                                "phone": "+34611111111",
                                "default_agent": "assistant",
                            },
                        ]
                    }
                }
            )
        )

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        assert config.whatsapp.tenants[0].wake_word is None

    def test_wake_word_different_values(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Different tenants can have different wake words."""
        config_file = tmp_path / ".whaagent.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "whatsapp": {
                        "tenants": [
                            {
                                "id": "t1",
                                "phone": "+1111111111",
                                "default_agent": "assistant",
                                "wake_word": "Jarvis",
                            },
                            {
                                "id": "t2",
                                "phone": "+2222222222",
                                "default_agent": "assistant",
                                "wake_word": "Alice",
                            },
                            {
                                "id": "t3",
                                "phone": "+3333333333",
                                "default_agent": "assistant",
                            },
                        ]
                    }
                }
            )
        )

        monkeypatch.setenv("whaagent_CONFIG", str(config_file))
        from whaagent.config import get_config

        config = get_config(force_reload=True)

        assert config.whatsapp.tenants[0].wake_word == "Jarvis"
        assert config.whatsapp.tenants[1].wake_word == "Alice"
        assert config.whatsapp.tenants[2].wake_word is None
