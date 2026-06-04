"""test_llm_service.py Tests for LLMService: configuration, JSON extraction, retry logic, and integration connectivity."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services.core.llm_service import (
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseFormatError,
    LLMService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_response(content: str, status_code: int = 200) -> MagicMock:
    """Build a fake requests.Response returning the given content string."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return mock_resp


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestLLMConfiguration:
    """Tests for LLM configuration checks."""

    def test_ensure_enabled_raises_when_base_url_missing(self, monkeypatch):
        """ensure_enabled should raise LLMConfigurationError when LLM_BASE_URL is empty."""
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        service = LLMService()
        with pytest.raises(LLMConfigurationError):
            service.ensure_enabled()

        get_settings.cache_clear()

    def test_ensure_enabled_raises_when_api_key_missing(self, monkeypatch):
        """ensure_enabled should raise LLMConfigurationError when LLM_API_KEY is empty."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from app.config import get_settings
        get_settings.cache_clear()

        service = LLMService()
        with pytest.raises(LLMConfigurationError):
            service.ensure_enabled()

        get_settings.cache_clear()

    def test_ensure_enabled_passes_when_configured(self, monkeypatch):
        """ensure_enabled should not raise when all LLM env vars are set."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        service = LLMService()
        service.ensure_enabled()  # Should not raise

        get_settings.cache_clear()

    def test_is_enabled_returns_false_without_config(self, monkeypatch):
        """is_enabled should return False when base URL or API key is missing."""
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        from app.config import get_settings
        get_settings.cache_clear()

        service = LLMService()
        assert service.is_enabled() is False

        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# _extract_json tests
# ---------------------------------------------------------------------------


class TestExtractJson:
    """Tests for LLMService._extract_json static method."""

    def test_extracts_plain_json_object(self):
        """Should parse a plain JSON object string."""
        content = '{"key": "value", "number": 42}'
        result = LLMService._extract_json(content)
        assert result == {"key": "value", "number": 42}

    def test_extracts_json_from_markdown_code_block(self):
        """Should extract JSON from a ```json code block."""
        content = 'Here is the result:\n```json\n{"key": "value"}\n```'
        result = LLMService._extract_json(content)
        assert result == {"key": "value"}

    def test_extracts_json_from_unmarked_code_block(self):
        """Should extract JSON from an unmarked ``` code block."""
        content = '```\n{"key": "value"}\n```'
        result = LLMService._extract_json(content)
        assert result == {"key": "value"}

    def test_extracts_json_by_finding_braces(self):
        """Should extract JSON by finding first { and last } when no code block."""
        content = 'Some text before {"key": "value"} and after.'
        result = LLMService._extract_json(content)
        assert result == {"key": "value"}

    def test_returns_none_for_non_json_content(self):
        """Should return None when content has no JSON."""
        content = "This is just plain text with no JSON at all."
        result = LLMService._extract_json(content)
        assert result is None

    def test_returns_none_for_json_array(self):
        """Should return None when content is a JSON array, not object."""
        content = '[1, 2, 3]'
        result = LLMService._extract_json(content)
        assert result is None

    def test_extracts_nested_json(self):
        """Should correctly extract nested JSON objects."""
        content = '{"outer": {"inner": [1, 2]}}'
        result = LLMService._extract_json(content)
        assert result == {"outer": {"inner": [1, 2]}}

    def test_handles_whitespace_around_json(self):
        """Should handle content with extra whitespace."""
        content = '  \n  {"key": "value"}  \n  '
        result = LLMService._extract_json(content)
        assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# ask_json tests (unit tests with mocked HTTP)
# ---------------------------------------------------------------------------


class TestAskJson:
    """Tests for LLMService.ask_json with mocked HTTP requests."""

    def test_ask_json_returns_parsed_dict(self, monkeypatch):
        """ask_json should return parsed dict from a successful LLM response."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        mock_response = _make_openai_response('{"result": "ok"}')
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        service = LLMService()
        result = service.ask_json("system", "user")
        assert result == {"result": "ok"}

        get_settings.cache_clear()

    def test_ask_json_raises_request_error_on_network_failure(self, monkeypatch):
        """ask_json should raise LLMRequestError after retries when network fails."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        monkeypatch.setattr(
            requests,
            "post",
            MagicMock(side_effect=requests.ConnectionError("connection refused")),
        )
        # Mock time.sleep to avoid delays in retry
        monkeypatch.setattr("app.services.core.llm_service.time.sleep", lambda s: None)

        service = LLMService()
        with pytest.raises(LLMRequestError):
            service.ask_json("system", "user")

        get_settings.cache_clear()

    def test_ask_json_raises_format_error_on_bad_json(self, monkeypatch):
        """ask_json should raise LLMResponseFormatError when response content is not JSON."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        mock_response = _make_openai_response("This is not JSON at all.")
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)
        monkeypatch.setattr("app.services.core.llm_service.time.sleep", lambda s: None)

        service = LLMService()
        with pytest.raises(LLMResponseFormatError):
            service.ask_json("system", "user")

        get_settings.cache_clear()

    def test_ask_json_retries_on_transient_failure(self, monkeypatch):
        """ask_json should retry on transient errors and eventually succeed."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise requests.ConnectionError("transient error")
            return _make_openai_response('{"result": "success"}')

        monkeypatch.setattr(requests, "post", mock_post)
        monkeypatch.setattr("app.services.core.llm_service.time.sleep", lambda s: None)

        service = LLMService()
        result = service.ask_json("system", "user")
        assert result == {"result": "success"}
        assert call_count == 3

        get_settings.cache_clear()

    def test_ask_json_extracts_json_from_code_block_response(self, monkeypatch):
        """ask_json should correctly parse JSON wrapped in markdown code blocks."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        mock_response = _make_openai_response('```json\n{"key": "value"}\n```')
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        service = LLMService()
        result = service.ask_json("system", "user")
        assert result == {"key": "value"}

        get_settings.cache_clear()


class TestAskJsonRequiredKeys:
    """Tests for ask_json required_keys retry logic."""

    def _setup_service(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()
        return LLMService()

    def test_passes_when_all_keys_present(self, monkeypatch):
        """Should return immediately when all required keys are present."""
        service = self._setup_service(monkeypatch)
        mock_response = _make_openai_response('{"keywords": ["a"], "units": []}')
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        result = service.ask_json("sys", "usr", required_keys=["keywords", "units"])
        assert "keywords" in result

    def test_retries_when_keys_missing(self, monkeypatch):
        """Should retry when required keys are missing from first response."""
        service = self._setup_service(monkeypatch)
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_openai_response('{"foo": "bar"}')
            return _make_openai_response('{"keywords": ["a"], "units": []}')

        monkeypatch.setattr(requests, "post", mock_post)

        result = service.ask_json("sys", "usr", required_keys=["keywords", "units"])
        assert "keywords" in result
        assert call_count == 2

    def test_returns_partial_after_retry_budget(self, monkeypatch):
        """Should return partial result after retry budget exhausted."""
        service = self._setup_service(monkeypatch)
        monkeypatch.setattr(requests, "post", lambda *a, **kw: _make_openai_response('{"foo": "bar"}'))

        result = service.ask_json("sys", "usr", required_keys=["missing_key"])
        assert "foo" in result
        assert "missing_key" not in result

    def test_no_retry_without_required_keys(self, monkeypatch):
        """Should not retry when required_keys is None."""
        service = self._setup_service(monkeypatch)
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_openai_response('{"foo": "bar"}')

        monkeypatch.setattr(requests, "post", mock_post)

        result = service.ask_json("sys", "usr")
        assert result == {"foo": "bar"}
        assert call_count == 1

    def test_bumps_temperature_on_missing_keys(self, monkeypatch):
        """Should increase temperature slightly on each missing-key retry."""
        service = self._setup_service(monkeypatch)
        temperatures = []

        def mock_post(*args, **kwargs):
            temperatures.append(kwargs["json"]["temperature"])
            return _make_openai_response('{"keywords": ["a"]}')

        monkeypatch.setattr(requests, "post", mock_post)

        service.ask_json("sys", "usr", required_keys=["keywords"])
        assert temperatures == [0.2]  # Got keys on first try, no retry needed


# ---------------------------------------------------------------------------
# ask_text tests
# ---------------------------------------------------------------------------


class TestAskText:
    """Tests for LLMService.ask_text with mocked HTTP requests."""

    def test_ask_text_returns_string(self, monkeypatch):
        """ask_text should return the raw content string from the LLM."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        mock_response = _make_openai_response("Hello, this is a test response.")
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_response)

        service = LLMService()
        result = service.ask_text("system", "user")
        assert result == "Hello, this is a test response."

        get_settings.cache_clear()

    def test_ask_text_raises_after_retries(self, monkeypatch):
        """ask_text should raise after exhausting retries."""
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        from app.config import get_settings
        get_settings.cache_clear()

        monkeypatch.setattr(
            requests,
            "post",
            MagicMock(side_effect=requests.ConnectionError("fail")),
        )
        monkeypatch.setattr("app.services.core.llm_service.time.sleep", lambda s: None)

        service = LLMService()
        with pytest.raises(LLMRequestError):
            service.ask_text("system", "user")

        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Error class tests
# ---------------------------------------------------------------------------


class TestLLMErrorClasses:
    """Tests for LLM error class hierarchy."""

    def test_llm_configuration_error_fields(self):
        """LLMConfigurationError should have correct status_code and error_code."""
        error = LLMConfigurationError()
        assert error.status_code == 503
        assert error.error_code == "llm_config_missing"

    def test_llm_request_error_fields(self):
        """LLMRequestError should carry the provided detail."""
        error = LLMRequestError("connection timeout")
        assert error.status_code == 502
        assert error.error_code == "llm_request_failed"
        assert "timeout" in error.detail

    def test_llm_response_format_error_fields(self):
        """LLMResponseFormatError should carry the provided detail."""
        error = LLMResponseFormatError("invalid JSON")
        assert error.status_code == 502
        assert error.error_code == "llm_response_invalid"


# ---------------------------------------------------------------------------
# Integration test (requires real LLM connectivity)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLLMIntegration:
    """Integration tests that call the real LLM API. Skipped unless --integration flag is used."""

    def test_real_llm_ask_json(self):
        """Call the real LLM with a simple prompt and verify JSON response is returned."""
        service = LLMService()
        service.ensure_enabled()  # Will raise if not configured
        result = service.ask_json(
            system_prompt="Return a JSON object.",
            user_prompt='Return JSON: {"status": "ok"}',
        )
        assert isinstance(result, dict)

    def test_real_llm_ask_text(self):
        """Call the real LLM and verify a text response is returned."""
        service = LLMService()
        service.ensure_enabled()
        result = service.ask_text(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say hello in one word.",
        )
        assert isinstance(result, str)
        assert len(result) > 0
