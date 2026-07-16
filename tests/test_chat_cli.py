"""Tests for chat_cli module."""

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest
import typer
from typer.testing import CliRunner

from whaagent.config import whaagentConfig, WhatsAppTenantConfig

runner = CliRunner()


class TestMCPServerManager:
    """Tests for MCPServerManager class."""

    def test_start_starts_subprocess_when_toolkit_path_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """start() should start subprocess when whaagent_TOOLKIT_PATH is set and exists."""
        from whaagent.chat_cli import MCPServerManager

        # Set up environment
        toolkit_path = "/path/to/toolkit"
        monkeypatch.setenv("whaagent_TOOLKIT_PATH", toolkit_path)

        # Mock Path.exists to return True
        with patch("whaagent.chat_cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            # Mock subprocess.Popen
            mock_process = MagicMock()
            mock_process.pid = 12345

            with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
                # Mock atexit.register to avoid side effects
                with patch("atexit.register") as mock_atexit:
                    manager = MCPServerManager()
                    manager.start()

                    # Verify Popen was called with correct arguments
                    mock_popen.assert_called_once()
                    call_args = mock_popen.call_args
                    assert call_args[0][0] == ["uv", "run", "python", "-m", "agentic_toolkit"]
                    assert call_args[1]["start_new_session"] is True
                    assert call_args[1]["cwd"] == toolkit_path

                    # Verify process is set
                    assert manager.process is mock_process

                    # Verify atexit was registered
                    mock_atexit.assert_called_once_with(manager.stop)

    def test_start_skips_when_toolkit_path_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """start() should skip when whaagent_TOOLKIT_PATH is not set."""
        from whaagent.chat_cli import MCPServerManager

        # Ensure env var is not set
        monkeypatch.delenv("whaagent_TOOLKIT_PATH", raising=False)

        manager = MCPServerManager()
        manager.start()

        # Process should be None
        assert manager.process is None

    def test_start_skips_when_toolkit_path_does_not_exist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """start() should skip when whaagent_TOOLKIT_PATH doesn't exist."""
        from whaagent.chat_cli import MCPServerManager

        # Set up environment
        toolkit_path = "/nonexistent/path"
        monkeypatch.setenv("whaagent_TOOLKIT_PATH", toolkit_path)

        # Mock Path.exists to return False
        with patch("whaagent.chat_cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            manager = MCPServerManager()

            with patch("whaagent.chat_cli.logger") as mock_logger:
                manager.start()

                # Process should be None
                assert manager.process is None

                # Warning should be logged
                mock_logger.warning.assert_called_once()

    def test_stop_kills_running_process(self) -> None:
        """stop() should terminate and wait for running process."""
        from whaagent.chat_cli import MCPServerManager

        manager = MCPServerManager()

        # Create mock process
        mock_process = MagicMock()
        manager.process = mock_process

        manager.stop()

        # Verify terminate and wait were called
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)

        # Process should be None after stop
        assert manager.process is None

    def test_stop_is_safe_when_no_process(self) -> None:
        """stop() should be safe to call when process is None."""
        from whaagent.chat_cli import MCPServerManager

        manager = MCPServerManager()
        manager.process = None

        # Should not raise
        manager.stop()

        # Process should still be None
        assert manager.process is None

    def test_stop_kills_process_group_on_sigterm_failure(self) -> None:
        """stop() should use os.killpg if process.terminate raises OSError."""
        from whaagent.chat_cli import MCPServerManager

        manager = MCPServerManager()

        # Create mock process that raises OSError on terminate
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.terminate.side_effect = OSError("Process already terminated")
        manager.process = mock_process

        with patch("os.killpg") as mock_killpg:
            with patch("os.getpgid", return_value=12345) as mock_getpgid:
                manager.stop()

                # Verify getpgid was called with the pid
                mock_getpgid.assert_called_once_with(mock_process.pid)

                # Verify killpg was called with the process group ID
                mock_killpg.assert_called_once_with(12345, 9)  # 9 = SIGKILL

        # Process should be None after stop
        assert manager.process is None

    def test_stop_force_kills_on_timeout(self) -> None:
        """stop() should call kill() if wait() times out."""
        from whaagent.chat_cli import MCPServerManager

        manager = MCPServerManager()

        # Create mock process that times out on first wait, succeeds on second
        mock_process = MagicMock()
        wait_call_count = [0]

        def wait_side_effect(**kwargs: object) -> None:
            wait_call_count[0] += 1
            if wait_call_count[0] == 1:
                raise subprocess.TimeoutExpired(cmd="test", timeout=5)
            # Second call after kill() succeeds

        mock_process.wait.side_effect = wait_side_effect
        manager.process = mock_process

        manager.stop()

        # Verify kill was called
        mock_process.kill.assert_called_once()

        # Verify wait was called twice (once after terminate, once after kill)
        assert mock_process.wait.call_count == 2

        # Process should be None after stop
        assert manager.process is None


class TestFindTestTenant:
    """Tests for find_test_tenant function."""

    def test_finds_test_tenant_from_config(self) -> None:
        """Should find tenant with id 'test' from config."""
        from whaagent.chat_cli import find_test_tenant

        # Create config with test tenant
        test_tenant = WhatsAppTenantConfig(
            id="test",
            phone="+1555123456",
            default_agent="assistant",
            allowed_contacts=["+1555999999"],
        )
        other_tenant = WhatsAppTenantConfig(
            id="production",
            phone="+1555987654",
            default_agent="developer",
            allowed_contacts=[],
        )
        config = whaagentConfig()
        config.whatsapp.tenants = [other_tenant, test_tenant]

        result = find_test_tenant(config)

        assert result.id == "test"
        assert result.phone == "+1555123456"
        assert result.default_agent == "assistant"
        assert result.allowed_contacts == ["+1555999999"]

    def test_returns_default_when_not_configured(self) -> None:
        """Should return default tenant when 'test' tenant not in config."""
        from whaagent.chat_cli import find_test_tenant

        # Create config without test tenant
        config = whaagentConfig()
        config.whatsapp.tenants = []

        result = find_test_tenant(config)

        assert result.id == "test"
        assert result.phone == "+1555000000"
        assert result.default_agent == "assistant"
        assert result.allowed_contacts == ["+1555000000"]

    def test_calls_get_config_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should call get_config() when config is None."""
        from whaagent.chat_cli import find_test_tenant

        # Create a mock config
        mock_config = whaagentConfig()
        mock_config.whatsapp.tenants = []

        with patch("whaagent.chat_cli.get_config", return_value=mock_config) as mock_get_config:
            result = find_test_tenant(None)

            # Verify get_config was called
            mock_get_config.assert_called_once()

            # Should return default tenant
            assert result.id == "test"
            assert result.phone == "+1555000000"


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_test_tenant_id_constant(self) -> None:
        """TEST_TENANT_ID should be 'test'."""
        from whaagent.chat_cli import TEST_TENANT_ID

        assert TEST_TENANT_ID == "test"

    def test_test_tenant_phone_constant(self) -> None:
        """TEST_TENANT_PHONE should be '+1555000000'."""
        from whaagent.chat_cli import TEST_TENANT_PHONE

        assert TEST_TENANT_PHONE == "+1555000000"

    def test_test_api_key_constant(self) -> None:
        """TEST_API_KEY should be 'test-secret'."""
        from whaagent.chat_cli import TEST_API_KEY

        assert TEST_API_KEY == "test-secret"

    def test_default_toolbox_port_constant(self) -> None:
        """DEFAULT_TOOLBOX_PORT should be 8080."""
        from whaagent.chat_cli import DEFAULT_TOOLBOX_PORT

        assert DEFAULT_TOOLBOX_PORT == 8080

    def test_mcp_startup_timeout_constant(self) -> None:
        """MCP_STARTUP_TIMEOUT should be 15."""
        from whaagent.chat_cli import MCP_STARTUP_TIMEOUT

        assert MCP_STARTUP_TIMEOUT == 15


class TestSendChatMessage:
    """Tests for send_chat_message function."""

    def test_sends_message_with_correct_headers_and_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """send_chat_message should POST to webhook with correct headers and body."""
        from unittest.mock import AsyncMock, patch

        from whaagent.chat_cli import TEST_API_KEY, send_chat_message
        from whaagent.config import whaagentConfig, WhatsAppTenantConfig

        # Create test config with API key and test tenant
        config = whaagentConfig()
        config.auth.api_keys = {TEST_API_KEY: "test"}
        test_tenant = WhatsAppTenantConfig(
            id="test",
            phone="+1555000000",
            default_agent="assistant",
            allowed_contacts=["+1555000000"],
        )
        config.whatsapp.tenants = [test_tenant]

        # Mock agent
        mock_agent_response = "Mock agent response: Hello from assistant!"
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_response)
        mock_agent._ensure_initialized = AsyncMock(return_value=None)
        mock_agent_class = MagicMock(return_value=mock_agent)

        # Patch AgentRegistry methods
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.discover_agents",
            lambda: None,
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get",
            lambda name: mock_agent_class if name == "assistant" else None,
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get_mcp_servers",
            lambda name: [],
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get_tool_categories",
            lambda name: [],
        )

        # Mock WhatsApp registry to return the test tenant
        mock_registry = MagicMock()
        mock_registry.lookup_by_phone.return_value = "test"

        # Mock get_config in the whatsapp route to return our test config
        with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
            with patch("whaagent.api.routes.whatsapp.get_config", return_value=config):
                result = send_chat_message(message="Hello, test!", config=config)

        # Verify response
        assert result["response"] == mock_agent_response
        assert result["tenant_id"] == "test"

        # Verify agent was called with correct message
        mock_agent.run.assert_called_once_with(
            "Hello, test!", config={"configurable": {"thread_id": "whatsapp:test:+1555000000"}}
        )

    def test_uses_custom_agent_when_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """send_chat_message should use the custom agent when agent_name is provided."""
        from unittest.mock import AsyncMock, patch

        from whaagent.chat_cli import TEST_API_KEY, send_chat_message
        from whaagent.config import whaagentConfig, WhatsAppTenantConfig

        # Create test config with API key and test tenant
        config = whaagentConfig()
        config.auth.api_keys = {TEST_API_KEY: "test"}
        test_tenant = WhatsAppTenantConfig(
            id="test",
            phone="+1555000000",
            default_agent="assistant",  # Default is assistant
            allowed_contacts=["+1555000000"],
        )
        config.whatsapp.tenants = [test_tenant]

        # Mock chef agent
        mock_agent_response = "Mock chef response: Let's cook!"
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_response)
        mock_agent._ensure_initialized = AsyncMock(return_value=None)
        mock_agent_class = MagicMock(return_value=mock_agent)

        # Track which agent name was requested
        requested_agents = []

        def mock_get_agent(name):
            requested_agents.append(name)
            return mock_agent_class if name == "chef" else None

        # Patch AgentRegistry methods
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.discover_agents",
            lambda: None,
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get",
            mock_get_agent,
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get_mcp_servers",
            lambda name: [],
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get_tool_categories",
            lambda name: [],
        )

        # Mock WhatsApp registry to return the test tenant
        mock_registry = MagicMock()
        mock_registry.lookup_by_phone.return_value = "test"

        # Mock get_config in the whatsapp route to return our test config
        with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
            with patch("whaagent.api.routes.whatsapp.get_config", return_value=config):
                result = send_chat_message(message="Recipe please", config=config, agent_name="chef")

        # Verify response
        assert result["response"] == mock_agent_response
        assert result["tenant_id"] == "test"

        # Verify chef agent was requested
        assert "chef" in requested_agents

        # Verify agent was called with correct message
        mock_agent.run.assert_called_once_with(
            "Recipe please", config={"configurable": {"thread_id": "whatsapp:test:+1555000000"}}
        )

    def test_raises_runtime_error_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """send_chat_message should raise RuntimeError when response is not 200."""
        from unittest.mock import patch

        from whaagent.chat_cli import send_chat_message
        from whaagent.config import whaagentConfig, WhatsAppTenantConfig

        # Create test config with WRONG API key (auth will fail)
        config = whaagentConfig()
        config.auth.api_keys = {"wrong-api-key": "test"}  # Not TEST_API_KEY
        test_tenant = WhatsAppTenantConfig(
            id="test",
            phone="+1555000000",
            default_agent="assistant",
            allowed_contacts=["+1555000000"],
        )
        config.whatsapp.tenants = [test_tenant]

        # Mock WhatsApp registry
        mock_registry = MagicMock()
        mock_registry.lookup_by_phone.return_value = "test"

        # Mock get_config in the whatsapp route to return our test config
        with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
            with patch("whaagent.api.routes.whatsapp.get_config", return_value=config):
                with pytest.raises(RuntimeError) as exc_info:
                    send_chat_message(message="Hello", config=config)

        # Verify error message contains status code
        assert "401" in str(exc_info.value)


class TestChatCommand:
    """Tests for chat_command Typer command."""

    def test_chat_command_prints_response(self) -> None:
        """chat_command should print the response and exit with code 0."""
        from whaagent.chat_cli import chat_command

        # Create test app
        app = typer.Typer()
        app.command()(chat_command)

        # Mock dependencies
        with patch("whaagent.chat_cli.MCPServerManager") as mock_mcp_class:
            mock_mcp_instance = MagicMock()
            mock_mcp_class.return_value = mock_mcp_instance

            with patch(
                "whaagent.chat_cli.send_chat_message",
                return_value={"response": "Hello!", "tenant_id": "test"},
            ):
                with patch(
                    "whaagent.chat_cli.find_test_tenant",
                    return_value=WhatsAppTenantConfig(
                        id="test",
                        phone="+1555000000",
                        default_agent="assistant",
                        allowed_contacts=["+1555000000"],
                    ),
                ):
                    result = runner.invoke(app, ["Hello, test!"])

        # Verify exit code and output
        assert result.exit_code == 0
        assert "Hello!" in result.output

        # Verify MCP manager was started and stopped
        mock_mcp_instance.start.assert_called_once()
        mock_mcp_instance.stop.assert_called_once()

    def test_chat_command_with_verbose(self) -> None:
        """chat_command should configure debug logging with --verbose flag."""
        from whaagent.chat_cli import chat_command

        # Create test app
        app = typer.Typer()
        app.command()(chat_command)

        # Mock dependencies
        with patch("whaagent.chat_cli.MCPServerManager") as mock_mcp_class:
            mock_mcp_instance = MagicMock()
            mock_mcp_class.return_value = mock_mcp_instance

            with patch(
                "whaagent.chat_cli.send_chat_message",
                return_value={"response": "Response", "tenant_id": "test"},
            ):
                with patch(
                    "whaagent.chat_cli.find_test_tenant",
                    return_value=WhatsAppTenantConfig(
                        id="test",
                        phone="+1555000000",
                        default_agent="assistant",
                        allowed_contacts=["+1555000000"],
                    ),
                ):
                    with patch("whaagent.chat_cli.configure_chat_logging") as mock_log:
                        result = runner.invoke(app, ["Hello", "--verbose"])

        # Verify exit code
        assert result.exit_code == 0

        # Verify logging was configured with DEBUG level
        mock_log.assert_called_once_with("DEBUG")

    def test_chat_command_with_agent_override(self) -> None:
        """chat_command should pass agent_name to send_chat_message when --agent is used."""
        from whaagent.chat_cli import chat_command

        # Create test app
        app = typer.Typer()
        app.command()(chat_command)

        # Mock dependencies
        with patch("whaagent.chat_cli.MCPServerManager") as mock_mcp_class:
            mock_mcp_instance = MagicMock()
            mock_mcp_class.return_value = mock_mcp_instance

            with patch(
                "whaagent.chat_cli.send_chat_message",
                return_value={"response": "Chef response", "tenant_id": "test"},
            ) as mock_send:
                with patch(
                    "whaagent.chat_cli.find_test_tenant",
                    return_value=WhatsAppTenantConfig(
                        id="test",
                        phone="+1555000000",
                        default_agent="assistant",
                        allowed_contacts=["+1555000000"],
                    ),
                ):
                    result = runner.invoke(app, ["Recipe please", "--agent", "chef"])

        # Verify exit code
        assert result.exit_code == 0

        # Verify send_chat_message was called with agent_name="chef"
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs.get("agent_name") == "chef"

    def test_chat_command_handles_error(self) -> None:
        """chat_command should print error in red and exit with code 1 on error."""
        from whaagent.chat_cli import chat_command

        # Create test app
        app = typer.Typer()
        app.command()(chat_command)

        # Mock dependencies
        with patch("whaagent.chat_cli.MCPServerManager") as mock_mcp_class:
            mock_mcp_instance = MagicMock()
            mock_mcp_class.return_value = mock_mcp_instance

            with patch(
                "whaagent.chat_cli.send_chat_message",
                side_effect=RuntimeError("Test error occurred"),
            ):
                with patch(
                    "whaagent.chat_cli.find_test_tenant",
                    return_value=WhatsAppTenantConfig(
                        id="test",
                        phone="+1555000000",
                        default_agent="assistant",
                        allowed_contacts=["+1555000000"],
                    ),
                ):
                    result = runner.invoke(app, ["Hello"])

        # Verify exit code is 1
        assert result.exit_code == 1

        # Verify error message is in output
        assert "Test error occurred" in result.output

        # Verify MCP manager was still stopped (in finally block)
        mock_mcp_instance.stop.assert_called_once()
