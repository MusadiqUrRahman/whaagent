"""Tests for LLM request timeout and model instance caching."""

import os
import threading
from unittest.mock import MagicMock, patch

import pytest

from whaagent.llm.providers import _MODEL_CACHE, _create_model, _get_request_timeout


@pytest.fixture(autouse=True)
def _clear_model_cache():
    """Clear the model cache before and after each test."""
    _MODEL_CACHE.clear()
    yield
    _MODEL_CACHE.clear()


class TestModelCaching:
    """Tests for model instance caching in providers.py."""

    @patch("whaagent.llm.providers.detect_provider", return_value="openai")
    def test_same_params_returns_cached_instance(self, mock_provider):
        """Calling _create_model twice with same params returns same instance."""
        mock_factory = MagicMock(return_value=MagicMock())

        with patch.dict("whaagent.llm.providers._FACTORIES", {"openai": mock_factory}):
            model1 = _create_model("gpt-4o-mini", 0.7)
            model2 = _create_model("gpt-4o-mini", 0.7)

        assert model1 is model2
        # Factory should only be called once (second call hits cache)
        assert mock_factory.call_count == 1

    @patch("whaagent.llm.providers.detect_provider", return_value="openai")
    def test_different_params_returns_different_instances(self, mock_provider):
        """Calling _create_model with different params creates separate instances."""
        mock_a = MagicMock()
        mock_b = MagicMock()
        mock_factory = MagicMock(side_effect=[mock_a, mock_b])

        with patch.dict("whaagent.llm.providers._FACTORIES", {"openai": mock_factory}):
            model1 = _create_model("gpt-4o-mini", 0.7)
            model2 = _create_model("gpt-4o-mini", 0.3)

        assert model1 is not model2
        assert mock_factory.call_count == 2

    @patch("whaagent.llm.providers.detect_provider", return_value="openai")
    def test_cache_key_includes_model_name(self, mock_provider):
        """Different model names produce different cache entries."""
        mock_a = MagicMock()
        mock_b = MagicMock()
        mock_factory = MagicMock(side_effect=[mock_a, mock_b])

        with patch.dict("whaagent.llm.providers._FACTORIES", {"openai": mock_factory}):
            model1 = _create_model("gpt-4o-mini", 0.7)
            model2 = _create_model("gpt-4o", 0.7)

        assert model1 is not model2
        assert mock_factory.call_count == 2

    @patch("whaagent.llm.providers.detect_provider", return_value="openai")
    def test_cache_populated_after_first_call(self, mock_provider):
        """Model cache is populated after the first _create_model call."""
        mock_factory = MagicMock(return_value=MagicMock())

        with patch.dict("whaagent.llm.providers._FACTORIES", {"openai": mock_factory}):
            _create_model("gpt-4o-mini", 0.7)

        assert ("gpt-4o-mini", 0.7, "openai") in _MODEL_CACHE

    @patch("whaagent.llm.providers.detect_provider", return_value="openai")
    @patch("whaagent.llm.providers._is_glm_model", return_value=True)
    def test_glm_routing_uses_cache(self, mock_glm, mock_provider):
        """GLM/z.ai smart routing path also populates the cache."""
        mock_model = MagicMock()
        with (
            patch.dict("os.environ", {"OPENAI_BASE_URL": "https://api.z.ai/v4", "OPENAI_API_KEY": "test"}),
            patch("whaagent.llm.providers._create_openai", return_value=mock_model),
        ):
            model1 = _create_model("glm-4.7", 0.7)
            model2 = _create_model("glm-4.7", 0.7)

        assert model1 is model2
        assert ("glm-4.7", 0.7, "openai") in _MODEL_CACHE


class TestRequestTimeout:
    """Tests for LLM request timeout configuration."""

    @patch.dict("os.environ", {}, clear=False)
    def test_default_request_timeout_is_60(self):
        """Default request timeout should be 60 seconds."""
        os.environ.pop("OPENAI_REQUEST_TIMEOUT", None)
        assert _get_request_timeout() == 60

    @patch.dict("os.environ", {"OPENAI_REQUEST_TIMEOUT": "30"})
    def test_request_timeout_from_env_var(self):
        """OPENAI_REQUEST_TIMEOUT env var overrides the default."""
        assert _get_request_timeout() == 30

    @patch.dict("os.environ", {"OPENAI_REQUEST_TIMEOUT": "abc"})
    def test_request_timeout_invalid_value_falls_back(self):
        """Invalid OPENAI_REQUEST_TIMEOUT falls back to default gracefully."""
        assert _get_request_timeout() == 60

    @patch.dict("os.environ", {"OPENAI_REQUEST_TIMEOUT": "30.5"})
    def test_request_timeout_float_value_falls_back(self):
        """Float OPENAI_REQUEST_TIMEOUT falls back to default gracefully."""
        assert _get_request_timeout() == 60


class TestModelCacheThreadSafety:
    """Tests for thread safety of model instance cache."""

    @patch("whaagent.llm.providers.detect_provider", return_value="openai")
    def test_concurrent_access_same_key(self, mock_provider):
        """Multiple threads creating the same model don't corrupt the cache."""
        call_count = 0

        def counting_factory(name: str, temp: float) -> MagicMock:
            nonlocal call_count
            call_count += 1
            return MagicMock()

        mock_factory = counting_factory

        with patch.dict("whaagent.llm.providers._FACTORIES", {"openai": mock_factory}):
            results = []
            errors = []

            def worker():
                try:
                    results.append(_create_model("gpt-4o-mini", 0.7))
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 10
        # All results should be valid MagicMock instances
        assert all(r is not None for r in results)
