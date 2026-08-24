import json
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Optional

from app.models.exception_record import ExceptionCategory
from app.models.llm_result import LLMEvidenceItem, LLMInvestigationResult, RecommendedAction

logger = logging.getLogger(__name__)

INVESTIGATION_SYSTEM_PROMPT = """You are a senior financial reconciliation investigator for Project Sentinel.
Your task is to analyze evidence from three financial feeds (Payment Gateway, Internal Ledger, Bank Statement) to determine the exact root cause of a reconciliation exception.

STRICT INVARIANTS:
1. Transaction evidence provided is AUTHORITATIVE. Do not invent transaction IDs, amounts, or facts.
2. Do not calculate unsupported financial figures. Use only the amounts and deltas provided in the evidence.
3. Distinguish directly observed evidence from inferences.
4. If the evidence is inconclusive, state uncertainty clearly, set requires_human_review=true, and set recommended_action='escalate_manual'.
5. Your response MUST be a single valid JSON object matching the requested schema. Do NOT enclose in backticks or markdown if possible.

ALLOWED CLASSIFICATIONS (must be exact string):
- "duplicate_entry"
- "fee_mismatch"
- "currency_rounding"
- "partial_refund"
- "delayed_settlement"
- "wrong_reference"
- "ambiguous_match"
- "unexplained"

ALLOWED RECOMMENDED ACTIONS:
- "approve_match"
- "flag_duplicate"
- "request_credit_note"
- "escalate_manual"
- "write_off"
- "investigate_further"
"""


class LLMClient(ABC):
    """Abstract interface for LLM reasoning provider."""

    @abstractmethod
    async def reason(self, context_dict: dict[str, Any]) -> LLMInvestigationResult:
        """Perform structured reasoning on investigation context."""
        pass


class FakeLLMClient(LLMClient):
    """Deterministic fake LLM client for testing and offline execution."""

    def __init__(
        self,
        canned_result: Optional[LLMInvestigationResult] = None,
        raise_error: Optional[Exception] = None,
    ):
        self.canned_result = canned_result
        self.raise_error = raise_error
        self.invocation_count = 0
        self.last_context: Optional[dict[str, Any]] = None

    async def reason(self, context_dict: dict[str, Any]) -> LLMInvestigationResult:
        self.invocation_count += 1
        self.last_context = context_dict

        if self.raise_error:
            raise self.raise_error

        if self.canned_result:
            return self.canned_result

        # Default smart fake response derived from context
        category_str = context_dict.get("category", "unexplained")
        try:
            category = ExceptionCategory(category_str)
        except ValueError:
            category = ExceptionCategory.UNEXPLAINED

        exposure_str = context_dict.get("financial_exposure", "0")
        exposure = Decimal(str(exposure_str))

        return LLMInvestigationResult(
            root_cause=f"Automated semantic investigation established root cause: {category.value}",
            classification=category.value,
            confidence=0.85,
            evidence=[
                LLMEvidenceItem(
                    observation=f"Investigated {len(context_dict.get('transactions', []))} involved transactions",
                    source="reconciliation_evidence",
                    relevance=f"Supports classification as {category.value}",
                )
            ],
            financial_exposure=exposure,
            recommended_action=RecommendedAction.ESCALATE_MANUAL if category == ExceptionCategory.UNEXPLAINED else RecommendedAction.APPROVE_MATCH,
            requires_human_review=category == ExceptionCategory.UNEXPLAINED,
            reasoning_summary=f"Evaluated multi-source evidence against historical patterns for {category.value}.",
        )


class GeminiLLMClient(LLMClient):
    """Google Gemini LLM client implementing strict structured JSON reasoning."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.0,
        timeout_seconds: float = 30.0,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    async def reason(self, context_dict: dict[str, Any]) -> LLMInvestigationResult:
        """Call Gemini model with structured schema output."""
        prompt = (
            f"{INVESTIGATION_SYSTEM_PROMPT}\n\n"
            f"--- INVESTIGATION CONTEXT ---\n"
            f"{json.dumps(context_dict, indent=2)}\n\n"
            f"Provide your JSON investigation result:"
        )

        try:
            # We attempt import of Google Generative AI SDK if available
            import os
            api_key = self.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                logger.warning("No Gemini API key configured. Using local deterministic fallback.")
                fake = FakeLLMClient()
                return await fake.reason(context_dict)

            # If google.generativeai is installed, make async call
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={"temperature": self.temperature, "response_mime_type": "application/json"},
            )
            response = await model.generate_content_async(prompt)
            raw_text = response.text.strip()
            # Clean possible markdown wrapping
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed_json = json.loads(raw_text.strip())
            return LLMInvestigationResult(**parsed_json)

        except Exception as e:
            logger.error(f"Gemini LLM call failed: {e}. Raising for fallback handling.")
            raise e


class GroqLLMClient(LLMClient):
    """Groq LLM client implementing structured JSON reasoning via the Groq API.

    Configuration is read exclusively from environment variables:
        GROQ_API_KEY  — required; Groq API key (never hardcoded or logged)
        GROQ_MODEL    — optional; defaults to "llama3-8b-8192"
    """

    _DEFAULT_MODEL = "llama3-8b-8192"
    _DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT,
    ):
        import os
        # API key: caller-supplied takes priority (allows DI in tests), then env
        self._api_key: str | None = api_key or os.environ.get("GROQ_API_KEY") or None
        # Model: caller-supplied, then env, then default
        self._model_name: str = (
            model_name
            or os.environ.get("GROQ_MODEL")
            or self._DEFAULT_MODEL
        )
        self._timeout_seconds: float = timeout_seconds

    async def reason(self, context_dict: dict[str, Any]) -> LLMInvestigationResult:
        """Call Groq with a structured JSON prompt and validate the response."""
        if not self._api_key:
            logger.warning("GROQ_API_KEY not configured. Falling back to FakeLLMClient.")
            return await FakeLLMClient().reason(context_dict)

        prompt = (
            f"{INVESTIGATION_SYSTEM_PROMPT}\n\n"
            f"--- INVESTIGATION CONTEXT ---\n"
            f"{json.dumps(context_dict, indent=2)}\n\n"
            f"Provide your JSON investigation result:"
        )

        try:
            from groq import AsyncGroq

            client = AsyncGroq(
                api_key=self._api_key,
                timeout=self._timeout_seconds,
            )

            response = await client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": INVESTIGATION_SYSTEM_PROMPT},
                    {"role": "user", "content": (
                        f"--- INVESTIGATION CONTEXT ---\n"
                        f"{json.dumps(context_dict, indent=2)}\n\n"
                        f"Provide your JSON investigation result:"
                    )},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            raw_text = response.choices[0].message.content
            if raw_text is None:
                raise ValueError("Groq returned an empty response content.")

            raw_text = raw_text.strip()
            # Strip any accidental markdown wrapping
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed_json = json.loads(raw_text.strip())
            # Run through the existing Pydantic validation firewall
            result = LLMInvestigationResult(**parsed_json)
            return result

        except Exception as e:
            logger.error("Groq LLM call failed: %s. Raising for fallback handling.", type(e).__name__)
            raise

