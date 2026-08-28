import json
import logging
import os
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
5. Your response MUST be a single valid JSON object with all required fields. Do NOT enclose in markdown fences.

ALLOWED CLASSIFICATIONS (must be exact string):
- "duplicate_entry"
- "fee_mismatch"
- "currency_rounding"
- "partial_refund"
- "delayed_settlement"
- "wrong_reference"
- "ambiguous_match"
- "unexplained"

ALLOWED RECOMMENDED ACTIONS (must be exact string):
- "approve_match"
- "flag_duplicate"
- "request_credit_note"
- "escalate_manual"
- "write_off"
- "investigate_further"

MANDATORY JSON FIELDS (all required):
- "root_cause": string (10 to 500 characters) describing the precise root cause.
- "classification": string (one of the allowed classifications).
- "confidence": float between 0.0 and 1.0.
- "evidence": array of objects, each containing:
    - "observation": string (factual data point)
    - "source": string (e.g. "gateway", "ledger", "bank", "historical")
    - "relevance": string (how it supports the conclusion)
- "financial_exposure": string or number representing total monetary amount at risk.
- "recommended_action": string (one of the allowed actions).
- "requires_human_review": boolean (true if ambiguous, high risk, or unexplained).
- "reasoning_summary": string (20 to 1500 characters) step-by-step rationale.
"""


class LLMClient(ABC):
    """Abstract interface for LLM reasoning and text synthesis providers."""

    @abstractmethod
    async def reason(self, context_dict: dict[str, Any]) -> LLMInvestigationResult:
        """Perform structured reasoning on investigation context."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> str:
        """Generate natural language text synthesis over verified data facts."""
        pass


class FakeLLMClient(LLMClient):
    """Deterministic fake LLM client for testing and offline execution."""

    def __init__(
        self,
        canned_result: Optional[LLMInvestigationResult] = None,
        canned_text: Optional[str] = None,
        raise_error: Optional[Exception] = None,
    ):
        self.canned_result = canned_result
        self.canned_text = canned_text
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

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> str:
        self.invocation_count += 1
        if self.raise_error:
            raise self.raise_error
        if self.canned_text:
            return self.canned_text
        return f"Synthesized analysis based on verified financial data: {user_prompt[:100]}"


class GeminiLLMClient(LLMClient):
    """Google Gemini LLM client implementing strict structured JSON reasoning and synthesis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.0,
        timeout_seconds: float = 30.0,
    ):
        raw_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.api_key: str | None = raw_key.strip() if raw_key and raw_key.strip() else None
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
            if not self.api_key:
                logger.warning("No Gemini API key configured. Using local deterministic fallback.")
                fake = FakeLLMClient()
                return await fake.reason(context_dict)

            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={"temperature": self.temperature, "response_mime_type": "application/json"},
            )
            response = await model.generate_content_async(prompt)
            raw_text = response.text.strip()
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

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> str:
        """Generate text using Gemini."""
        if not self.api_key:
            return f"Deterministic synthesis: {user_prompt[:120]}"
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
            )
            response = await model.generate_content_async(user_prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini text generation failed: {e}")
            raise e


class GroqLLMClient(LLMClient):
    """Groq LLM client implementing structured JSON reasoning and factual text synthesis."""

    _DEFAULT_MODEL = "qwen/qwen3.8-27b"
    _DEFAULT_TIMEOUT = 15.0

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT,
    ):
        raw_key = api_key or os.environ.get("GROQ_API_KEY")
        self._api_key: str | None = raw_key.strip() if raw_key and raw_key.strip() else None
        self._model_name: str = (
            model_name
            or os.environ.get("GROQ_MODEL")
            or self._DEFAULT_MODEL
        )
        self._timeout_seconds: float = timeout_seconds

    @property
    def is_configured(self) -> bool:
        """Check whether a non-empty API key is present."""
        return bool(self._api_key)

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
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed_json = json.loads(raw_text.strip())
            result = LLMInvestigationResult(**parsed_json)
            return result

        except Exception as e:
            logger.error("Groq LLM call failed: %s. Raising for fallback handling.", type(e).__name__)
            raise

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> str:
        """Generate factual natural-language synthesis over verified PostgreSQL facts."""
        if not self._api_key:
            raise ValueError("GROQ_API_KEY is not configured.")

        from groq import AsyncGroq

        client = AsyncGroq(
            api_key=self._api_key,
            timeout=self._timeout_seconds,
        )

        response = await client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned empty text response.")
        return content.strip()
