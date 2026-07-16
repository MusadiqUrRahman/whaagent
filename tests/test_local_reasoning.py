"""Tests for whaagent package - Local Reasoning LLM provider."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from whaagent.llm.local_reasoning import LocalReasoningLLM, get_local_developer_model


class TestLocalReasoningLLM:
    """Test LocalReasoningLLM class for stripping reasoning tags."""

    def test_strips_thinking_tags_from_content(self):
        """Test LocalReasoningLLM strips <reasoning> tags from messages."""
        model = LocalReasoningLLM(
            openai_api_base="http://localhost:8080/v1",
            api_key="not-needed",
            model="test-model",
            temperature=0.2,
        )

        # Mock the parent _generate to return a controlled result
        mock_result = MagicMock()
        mock_generation = MagicMock()
        mock_message = AIMessage(content="<reasoning>Let me analyze this...\n\n</reasoning>Final answer is here!")
        mock_generation.message = mock_message
        mock_result.generations = [mock_generation]

        with patch.object(ChatOpenAI, "_generate", return_value=mock_result):
            messages = [HumanMessage(content="test")]
            result = model._generate(messages)

            assert result.generations[0].message.content == "Final answer is here!"
            assert "<reasoning>" not in result.generations[0].message.content

    def test_handles_content_without_thinking_tags(self):
        """Test LocalReasoningLLM leaves content unchanged when no reasoning tags present."""
        model = LocalReasoningLLM(
            openai_api_base="http://localhost:8080/v1",
            api_key="not-needed",
            model="test-model",
            temperature=0.2,
        )

        mock_result = MagicMock()
        mock_generation = MagicMock()
        mock_message = AIMessage(content="Just the answer, no reasoning.")
        mock_generation.message = mock_message
        mock_result.generations = [mock_generation]

        with patch.object(ChatOpenAI, "_generate", return_value=mock_result):
            messages = [HumanMessage(content="test")]
            result = model._generate(messages)

            assert result.generations[0].message.content == "Just the answer, no reasoning."

    def test_handles_empty_content_after_strip(self):
        """Test LocalReasoningLLM handles content that becomes empty after stripping."""
        model = LocalReasoningLLM(
            openai_api_base="http://localhost:8080/v1",
            api_key="not-needed",
            model="test-model",
            temperature=0.2,
        )

        mock_result = MagicMock()
        mock_generation = MagicMock()
        mock_message = AIMessage(content="<reasoning>Just reasoning, no answer...</reasoning>")
        mock_generation.message = mock_message
        mock_result.generations = [mock_generation]

        with patch.object(ChatOpenAI, "_generate", return_value=mock_result):
            messages = [HumanMessage(content="test")]
            result = model._generate(messages)

            assert result.generations[0].message.content == ""


class TestGetLocalDeveloperModel:
    """Test get_local_developer_model factory function."""

    def test_factory_creates_model_with_correct_config(self):
        """Test that get_local_developer_model creates model with correct configuration."""
        model = get_local_developer_model()

        assert model.openai_api_base == "http://localhost:8080/v1"
        assert model.model == "glm-4.7-flash"
        assert model.temperature == 0.2

    def test_factory_returns_local_reasoning_llm_instance(self):
        """Test that factory returns LocalReasoningLLM instance."""
        model = get_local_developer_model()

        assert isinstance(model, LocalReasoningLLM)
