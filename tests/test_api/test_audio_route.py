"""Tests for WhatsApp audio message endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import whaagent.api.routes.whatsapp as whatsapp_module
from whaagent.api.routes.whatsapp import get_whatsapp_registry
from whaagent.api.server import create_app  # type: ignore[import-untyped]


def _reset_whatsapp_registry() -> None:
    """Reset the global WhatsApp registry between tests."""
    whatsapp_module._whatsapp_registry = None


class TestAudioRoute:
    """Tests for the /api/v1/channels/whatsapp/audio endpoint."""

    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_audio_endpoint_missing_api_key(self, mock_config: MagicMock) -> None:
        """Test that missing API key returns 401."""
        _reset_whatsapp_registry()
        mock_config.return_value = MagicMock(auth=MagicMock(api_keys={"test-key": "tenant1"}))
        app = create_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/channels/whatsapp/audio",
            files={"audio": ("test.ogg", b"audio data", "audio/ogg")},
            data={"tenant_id": "t1", "phone": "1234567890", "mime_type": "audio/ogg"},
        )
        assert response.status_code == 401

    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_audio_endpoint_no_audio_file(self, mock_config: MagicMock) -> None:
        """Test that missing audio file returns 400."""
        _reset_whatsapp_registry()
        mock_config.return_value = MagicMock(auth=MagicMock(api_keys={"test-key": "tenant1"}))
        app = create_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/channels/whatsapp/audio",
            headers={"X-API-Key": "test-key"},
            data={"tenant_id": "t1", "phone": "1234567890"},
        )
        assert response.status_code == 400

    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_audio_endpoint_missing_phone(self, mock_config: MagicMock) -> None:
        """Test that missing phone returns 400."""
        _reset_whatsapp_registry()
        mock_config.return_value = MagicMock(auth=MagicMock(api_keys={"test-key": "tenant1"}))
        app = create_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/channels/whatsapp/audio",
            headers={"X-API-Key": "test-key"},
            files={"audio": ("test.ogg", b"audio data", "audio/ogg")},
            data={"tenant_id": "t1"},
        )
        assert response.status_code == 400

    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_audio_endpoint_tenant_not_found(self, mock_config: MagicMock) -> None:
        """Test that unknown phone returns 404."""
        _reset_whatsapp_registry()
        mock_config.return_value = MagicMock(
            auth=MagicMock(api_keys={"test-key": "tenant1"}),
            whatsapp=MagicMock(tenants=[]),
        )
        app = create_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/channels/whatsapp/audio",
            headers={"X-API-Key": "test-key"},
            files={"audio": ("test.ogg", b"audio data", "audio/ogg")},
            data={"phone": "9999999999", "mime_type": "audio/ogg"},
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


class TestAudioWakeWord:
    """Tests for wake word routing in the audio endpoint."""

    @patch("whaagent.api.routes.whatsapp.AgentRegistry")
    @patch("whaagent.api.routes.whatsapp.AudioTranscriptionCache")
    @patch("whaagent.api.routes.whatsapp.AudioTranscriber")
    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_audio_with_wake_word_routes_to_agent(
        self,
        mock_config: MagicMock,
        mock_transcriber_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_agent_registry: MagicMock,
    ) -> None:
        """Audio with wake word should be routed through the agent."""
        _reset_whatsapp_registry()
        mock_tenant = MagicMock()
        mock_tenant.id = "test-tenant"
        mock_tenant.phone = "+1234567890"
        mock_tenant.default_agent = "assistant"
        mock_tenant.allowed_contacts = None
        mock_tenant.wake_word = "Jarvis"

        mock_config.return_value = MagicMock(
            auth=MagicMock(api_keys={"test-key": "test-tenant"}),
            llm=MagicMock(model="gpt-4", temperature=0.7),
            whatsapp=MagicMock(tenants=[mock_tenant]),
            storage=MagicMock(base_path=None),
        )

        mock_registry_instance = MagicMock()
        mock_registry_instance.lookup_by_phone.return_value = "test-tenant"

        # Cache miss
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        # Transcriber returns text with wake word
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_audio = AsyncMock(return_value="Jarvis what's the weather")
        mock_transcriber_cls.return_value = mock_transcriber

        # Agent
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value="The weather is sunny")
        mock_agent_cls = MagicMock(return_value=mock_agent_instance)
        mock_agent_registry.get.return_value = mock_agent_cls
        mock_agent_registry.get_mcp_servers.return_value = []
        mock_agent_registry.get_tool_categories.return_value = []

        from whaagent.api.pool import TenantAgentPool

        app = create_app()
        app.state.agent_pool = TenantAgentPool(max_size=10)
        app.dependency_overrides[get_whatsapp_registry] = lambda: mock_registry_instance
        client = TestClient(app)
        response = client.post(
            "/api/v1/channels/whatsapp/audio",
            headers={"X-API-Key": "test-key"},
            files={"audio": ("test.ogg", b"audio data", "audio/ogg")},
            data={"phone": "+1234567890", "mime_type": "audio/ogg"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "The weather is sunny"
        # Verify agent.run was called with wake word stripped
        mock_agent_instance.run.assert_called_once()
        call_args = mock_agent_instance.run.call_args
        assert call_args[0][0] == "what's the weather"

    @patch("whaagent.api.routes.whatsapp.AudioTranscriptionCache")
    @patch("whaagent.api.routes.whatsapp.AudioTranscriber")
    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_audio_without_wake_word_returns_empty(
        self,
        mock_config: MagicMock,
        mock_transcriber_cls: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Audio without wake word should return empty response."""
        _reset_whatsapp_registry()
        mock_tenant = MagicMock()
        mock_tenant.id = "test-tenant"
        mock_tenant.phone = "+1234567890"
        mock_tenant.default_agent = "assistant"
        mock_tenant.allowed_contacts = None
        mock_tenant.wake_word = "Jarvis"

        mock_config.return_value = MagicMock(
            auth=MagicMock(api_keys={"test-key": "test-tenant"}),
            llm=MagicMock(model="gpt-4", temperature=0.7),
            whatsapp=MagicMock(tenants=[mock_tenant]),
            storage=MagicMock(base_path=None),
        )

        mock_registry_instance = MagicMock()
        mock_registry_instance.lookup_by_phone.return_value = "test-tenant"

        # Cache miss
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        # Transcriber returns text WITHOUT wake word
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_audio = AsyncMock(return_value="just talking to myself")
        mock_transcriber_cls.return_value = mock_transcriber

        app = create_app()
        app.dependency_overrides[get_whatsapp_registry] = lambda: mock_registry_instance
        client = TestClient(app)
        response = client.post(
            "/api/v1/channels/whatsapp/audio",
            headers={"X-API-Key": "test-key"},
            files={"audio": ("test.ogg", b"audio data", "audio/ogg")},
            data={"phone": "+1234567890", "mime_type": "audio/ogg"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == ""
        assert data["wake_word_matched"] == "false"

    @patch("whaagent.api.routes.whatsapp.AgentRegistry")
    @patch("whaagent.api.routes.whatsapp.AudioTranscriptionCache")
    @patch("whaagent.api.routes.whatsapp.AudioTranscriber")
    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_audio_no_wake_word_configured_routes_to_agent(
        self,
        mock_config: MagicMock,
        mock_transcriber_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_agent_registry: MagicMock,
    ) -> None:
        """Audio with no wake_word configured should always route to agent."""
        _reset_whatsapp_registry()
        mock_tenant = MagicMock()
        mock_tenant.id = "test-tenant"
        mock_tenant.phone = "+1234567890"
        mock_tenant.default_agent = "assistant"
        mock_tenant.allowed_contacts = None
        mock_tenant.wake_word = None  # No wake word configured

        mock_config.return_value = MagicMock(
            auth=MagicMock(api_keys={"test-key": "test-tenant"}),
            llm=MagicMock(model="gpt-4", temperature=0.7),
            whatsapp=MagicMock(tenants=[mock_tenant]),
            storage=MagicMock(base_path=None),
        )

        mock_registry_instance = MagicMock()
        mock_registry_instance.lookup_by_phone.return_value = "test-tenant"

        # Cache miss
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_audio = AsyncMock(return_value="hello there")
        mock_transcriber_cls.return_value = mock_transcriber

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value="Hi!")
        mock_agent_cls = MagicMock(return_value=mock_agent_instance)
        mock_agent_registry.get.return_value = mock_agent_cls
        mock_agent_registry.get_mcp_servers.return_value = []
        mock_agent_registry.get_tool_categories.return_value = []

        from whaagent.api.pool import TenantAgentPool

        app = create_app()
        app.state.agent_pool = TenantAgentPool(max_size=10)
        app.dependency_overrides[get_whatsapp_registry] = lambda: mock_registry_instance
        client = TestClient(app)
        response = client.post(
            "/api/v1/channels/whatsapp/audio",
            headers={"X-API-Key": "test-key"},
            files={"audio": ("test.ogg", b"audio data", "audio/ogg")},
            data={"phone": "+1234567890", "mime_type": "audio/ogg"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hi!"
        mock_agent_instance.run.assert_called_once()

    @patch("whaagent.api.routes.whatsapp.AudioTranscriptionCache")
    @patch("whaagent.api.routes.whatsapp.AudioTranscriber")
    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_audio_only_wake_word_returns_empty(
        self,
        mock_config: MagicMock,
        mock_transcriber_cls: MagicMock,
        mock_cache_cls: MagicMock,
    ) -> None:
        """Audio that is only the wake word returns empty response."""
        _reset_whatsapp_registry()
        mock_tenant = MagicMock()
        mock_tenant.id = "test-tenant"
        mock_tenant.phone = "+1234567890"
        mock_tenant.default_agent = "assistant"
        mock_tenant.allowed_contacts = None
        mock_tenant.wake_word = "Jarvis"

        mock_config.return_value = MagicMock(
            auth=MagicMock(api_keys={"test-key": "test-tenant"}),
            llm=MagicMock(model="gpt-4", temperature=0.7),
            whatsapp=MagicMock(tenants=[mock_tenant]),
            storage=MagicMock(base_path=None),
        )

        mock_registry_instance = MagicMock()
        mock_registry_instance.lookup_by_phone.return_value = "test-tenant"

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_audio = AsyncMock(return_value="Jarvis")
        mock_transcriber_cls.return_value = mock_transcriber

        app = create_app()
        app.dependency_overrides[get_whatsapp_registry] = lambda: mock_registry_instance
        client = TestClient(app)
        response = client.post(
            "/api/v1/channels/whatsapp/audio",
            headers={"X-API-Key": "test-key"},
            files={"audio": ("test.ogg", b"audio data", "audio/ogg")},
            data={"phone": "+1234567890", "mime_type": "audio/ogg"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == ""
        assert data["wake_word_matched"] == "true"
