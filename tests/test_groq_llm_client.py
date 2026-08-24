"""Tests for GroqLLMClient.

All tests use mocks — no real Groq API call is made during pytest.
FakeLLMClient is verified to remain unchanged.
"""

import json
import os
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.investigation.llm_client import FakeLLMClient, GroqLLMClient, LLMClient
from app.models.llm_result import LLMEvidenceItem, LLMInvestigationResult, RecommendedAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_llm_result_dict() -> dict:
    """Return a dict that passes LLMInvestigationResult validation."""
    return {
        "root_cause": "Test root cause for reconciliation exception analysis",
        "classification": "fee_mismatch",
        "confidence": 0.91,
        "evidence": [
            {
                "observation": "Gateway charged 20.00 fee; ledger shows 0.00",
                "source": "gateway",
                "relevance": "Direct cause of the mismatch",
            }
        ],
        "financial_exposure": "20.00",
        "recommended_action": "request_credit_note",
        "requires_human_review": False,
        "reasoning_summary": "Fee discrepancy between gateway and ledger confirmed. No ambiguity in the data.",
    }


def _sample_context() -> dict[str, Any]:
    return {"category": "fee_mismatch", "transactions": [], "financial_exposure": "20.00"}


def _make_mock_groq_response(content: str) -> MagicMock:
    """Build a mock Groq chat completion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# 1. Configuration loading
# ---------------------------------------------------------------------------

class TestGroqClientConfiguration:
    """GROQ_API_KEY must come from environment; no key must ever be hardcoded."""

    def test_reads_api_key_from_environment(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key-from-env")
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        client = GroqLLMClient()
        assert client._api_key == "test-key-from-env"

    def test_reads_model_from_environment(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "any-key")
        monkeypatch.setenv("GROQ_MODEL", "mixtral-8x7b-32768")
        client = GroqLLMClient()
        assert client._model_name == "mixtral-8x7b-32768"

    def test_default_model_when_env_not_set(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "any-key")
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        client = GroqLLMClient()
        assert client._model_name == GroqLLMClient._DEFAULT_MODEL

    def test_caller_supplied_key_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "env-key")
        client = GroqLLMClient(api_key="caller-key")
        assert client._api_key == "caller-key"

    def test_caller_supplied_model_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_MODEL", "env-model")
        client = GroqLLMClient(api_key="k", model_name="caller-model")
        assert client._model_name == "caller-model"

    def test_api_key_not_hardcoded_in_source(self):
        """Verify no literal API key appears in the source file."""
        import inspect
        import app.investigation.llm_client as module
        source = inspect.getsource(module)
        # Hardcoded keys start with "gsk_" for Groq
        assert "gsk_" not in source, "Groq API key must not be hardcoded in source"

    def test_implements_llm_client_interface(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()
        assert isinstance(client, LLMClient)


# ---------------------------------------------------------------------------
# 2. Valid response parsing
# ---------------------------------------------------------------------------

class TestGroqClientValidResponse:
    """Mock Groq, return valid JSON, verify Pydantic validation passes."""

    @pytest.mark.asyncio
    async def test_valid_response_returns_llm_investigation_result(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()

        mock_response = _make_mock_groq_response(json.dumps(_valid_llm_result_dict()))

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await client.reason(_sample_context())

        assert isinstance(result, LLMInvestigationResult)
        assert result.classification == "fee_mismatch"
        assert result.confidence == pytest.approx(0.91)
        assert result.recommended_action == RecommendedAction.REQUEST_CREDIT_NOTE
        assert result.requires_human_review is False
        assert len(result.evidence) == 1

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fence_from_response(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()

        wrapped = f"```json\n{json.dumps(_valid_llm_result_dict())}\n```"
        mock_response = _make_mock_groq_response(wrapped)

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await client.reason(_sample_context())

        assert isinstance(result, LLMInvestigationResult)

    @pytest.mark.asyncio
    async def test_structured_json_output_requested(self, monkeypatch):
        """Verify response_format=json_object is passed to the Groq client."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()

        mock_response = _make_mock_groq_response(json.dumps(_valid_llm_result_dict()))

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            await client.reason(_sample_context())
            call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
            assert call_kwargs["response_format"] == {"type": "json_object"}


# ---------------------------------------------------------------------------
# 3. Invalid / malformed response
# ---------------------------------------------------------------------------

class TestGroqClientInvalidResponse:
    """Malformed LLM output must be rejected by the Pydantic validation firewall."""

    @pytest.mark.asyncio
    async def test_invalid_classification_rejected(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()

        bad = _valid_llm_result_dict()
        bad["classification"] = "not_a_real_category"
        mock_response = _make_mock_groq_response(json.dumps(bad))

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception):
                await client.reason(_sample_context())

    @pytest.mark.asyncio
    async def test_missing_required_field_rejected(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()

        bad = _valid_llm_result_dict()
        del bad["root_cause"]
        mock_response = _make_mock_groq_response(json.dumps(bad))

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception):
                await client.reason(_sample_context())

    @pytest.mark.asyncio
    async def test_non_json_response_rejected(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()

        mock_response = _make_mock_groq_response("Sorry, I cannot help with that.")

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception):
                await client.reason(_sample_context())

    @pytest.mark.asyncio
    async def test_empty_content_rejected(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()

        mock_response = _make_mock_groq_response(None)

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception):
                await client.reason(_sample_context())


# ---------------------------------------------------------------------------
# 4. Provider / API failure handling
# ---------------------------------------------------------------------------

class TestGroqClientProviderFailure:
    """API-level exceptions must propagate as exceptions (not silently swallowed)."""

    @pytest.mark.asyncio
    async def test_groq_api_exception_propagates(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient()

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(
                side_effect=RuntimeError("Connection refused")
            )

            with pytest.raises(RuntimeError, match="Connection refused"):
                await client.reason(_sample_context())

    @pytest.mark.asyncio
    async def test_timeout_exception_propagates(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        client = GroqLLMClient(timeout_seconds=5.0)

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(
                side_effect=TimeoutError("Request timed out")
            )

            with pytest.raises(TimeoutError):
                await client.reason(_sample_context())

    @pytest.mark.asyncio
    async def test_no_api_key_falls_back_to_fake_client(self, monkeypatch):
        """When GROQ_API_KEY is absent, GroqLLMClient safely falls back to FakeLLMClient."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        client = GroqLLMClient(api_key=None)

        result = await client.reason(_sample_context())
        # FakeLLMClient produces a valid LLMInvestigationResult
        assert isinstance(result, LLMInvestigationResult)


# ---------------------------------------------------------------------------
# 5. FakeLLMClient is unchanged
# ---------------------------------------------------------------------------

class TestFakeLLMClientUnchanged:
    """Existing FakeLLMClient behavior must remain intact."""

    @pytest.mark.asyncio
    async def test_fake_client_returns_valid_result(self):
        client = FakeLLMClient()
        result = await client.reason(_sample_context())
        assert isinstance(result, LLMInvestigationResult)
        assert result.confidence == 0.85
        assert len(result.evidence) >= 1

    @pytest.mark.asyncio
    async def test_fake_client_tracks_invocation_count(self):
        client = FakeLLMClient()
        await client.reason(_sample_context())
        await client.reason(_sample_context())
        assert client.invocation_count == 2

    @pytest.mark.asyncio
    async def test_fake_client_canned_result_used(self):
        canned = LLMInvestigationResult(
            root_cause="Canned root cause for testing purposes",
            classification="duplicate_entry",
            confidence=0.99,
            evidence=[LLMEvidenceItem(
                observation="Test observation",
                source="test",
                relevance="test relevance",
            )],
            financial_exposure=Decimal("0"),
            recommended_action=RecommendedAction.FLAG_DUPLICATE,
            requires_human_review=False,
            reasoning_summary="Test canned reasoning summary for this unit test scenario.",
        )
        client = FakeLLMClient(canned_result=canned)
        result = await client.reason(_sample_context())
        assert result.classification == "duplicate_entry"
        assert result.confidence == 0.99

    @pytest.mark.asyncio
    async def test_fake_client_raises_configured_error(self):
        client = FakeLLMClient(raise_error=ValueError("configured error"))
        with pytest.raises(ValueError, match="configured error"):
            await client.reason(_sample_context())

    def test_fake_client_is_llm_client_subclass(self):
        assert isinstance(FakeLLMClient(), LLMClient)


# ---------------------------------------------------------------------------
# 6. Security: no credentials in logs
# ---------------------------------------------------------------------------

class TestGroqClientSecurity:
    """API key must never appear in log output."""

    @pytest.mark.asyncio
    async def test_api_key_not_in_error_logs(self, monkeypatch, caplog):
        import logging
        monkeypatch.setenv("GROQ_API_KEY", "super-secret-key-xyz")
        client = GroqLLMClient()

        with patch("groq.AsyncGroq") as MockAsyncGroq:
            mock_instance = AsyncMock()
            MockAsyncGroq.return_value = mock_instance
            mock_instance.chat.completions.create = AsyncMock(
                side_effect=RuntimeError("API error")
            )
            with caplog.at_level(logging.ERROR, logger="app.investigation.llm_client"):
                with pytest.raises(RuntimeError):
                    await client.reason(_sample_context())

        for record in caplog.records:
            assert "super-secret-key-xyz" not in record.getMessage()
