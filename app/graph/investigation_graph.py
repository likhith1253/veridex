import logging
from decimal import Decimal
from typing import Any, Optional

from langgraph.graph import END, StateGraph

from app.graph.state import InvestigationStage, InvestigationState
from app.investigation.analyzer import DeterministicAnalyzer
from app.investigation.evidence import InvestigationContextBuilder
from app.investigation.exposure import ExposureCalculator
from app.investigation.llm_client import FakeLLMClient, LLMClient
from app.investigation.retrieval import FakeHistoricalRetriever, HistoricalRetriever
from app.models.decision_result import DecisionResult
from app.models.exception_record import ExceptionCategory
from app.models.investigation_result import (
    InvestigationConclusion,
    InvestigationMethod,
    InvestigationStatus,
)
from app.models.llm_result import LLMInvestigationResult
from app.models.transaction import Transaction
from app.risk.calculator import RiskCalculator
from app.risk.interface import RiskInput

logger = logging.getLogger(__name__)


class InvestigationGraphRunner:
    """Orchestrates the LangGraph investigation state machine."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        retriever: Optional[HistoricalRetriever] = None,
    ):
        self.llm_client = llm_client or FakeLLMClient()
        self.retriever = retriever or FakeHistoricalRetriever()
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(InvestigationState)

        # Register nodes
        workflow.add_node("collect_evidence", self._node_collect_evidence)
        workflow.add_node("deterministic_analysis", self._node_deterministic_analysis)
        workflow.add_node("calculate_risk", self._node_calculate_risk)
        workflow.add_node("retrieve_history", self._node_retrieve_history)
        workflow.add_node("llm_reasoning", self._node_llm_reasoning)
        workflow.add_node("validate_llm_output", self._node_validate_llm_output)
        workflow.add_node("finalize_conclusion", self._node_finalize_conclusion)

        # Set entry point
        workflow.set_entry_point("collect_evidence")

        # Standard linear transitions
        workflow.add_edge("collect_evidence", "deterministic_analysis")
        workflow.add_edge("deterministic_analysis", "calculate_risk")

        # Conditional branch after risk calculation
        workflow.add_conditional_edges(
            "calculate_risk",
            self._route_after_risk,
            {
                "retrieve_history": "retrieve_history",
                "finalize_conclusion": "finalize_conclusion",
            },
        )

        workflow.add_edge("retrieve_history", "llm_reasoning")

        # Conditional branch after LLM reasoning
        workflow.add_conditional_edges(
            "llm_reasoning",
            self._route_after_llm,
            {
                "validate_llm_output": "validate_llm_output",
                "finalize_conclusion": "finalize_conclusion",
            },
        )

        workflow.add_edge("validate_llm_output", "finalize_conclusion")
        workflow.add_edge("finalize_conclusion", END)

        return workflow.compile()

    # --- Node Implementations ---

    async def _node_collect_evidence(self, state: InvestigationState) -> dict[str, Any]:
        """Convert raw state dictionary into structured InvestigationEvidence."""
        transactions = [Transaction(**t) for t in state.transactions]
        decision = DecisionResult(**state.decision) if state.decision else None

        ctx = InvestigationContextBuilder.build(
            exception_id=state.exception_id,
            run_id=state.run_id,
            transactions=transactions,
            decision=decision,
        )

        return {
            "transaction_evidence": ctx.evidence.to_dict(),
            "stage": InvestigationStage.EVIDENCE_READY,
        }

    async def _node_deterministic_analysis(self, state: InvestigationState) -> dict[str, Any]:
        """Apply deterministic financial rules to establish preliminary root cause."""
        transactions = [Transaction(**t) for t in state.transactions]
        decision = DecisionResult(**state.decision) if state.decision else None

        ctx = InvestigationContextBuilder.build(
            exception_id=state.exception_id,
            run_id=state.run_id,
            transactions=transactions,
            decision=decision,
        )

        result = DeterministicAnalyzer.analyze(ctx.evidence, transactions, decision)

        return {
            "classified_category": result.detected_category.value,
            "deterministic_confidence": str(result.confidence),
            "root_cause": result.root_cause,
            "explanation": result.explanation,
            "recommended_action": result.recommended_action,
            "amount_delta": str(ctx.evidence.max_amount_delta),
            "is_duplicate": ctx.evidence.has_duplicate_identifiers,
            "requires_human_review": result.detected_category == ExceptionCategory.UNEXPLAINED,
            "stage": InvestigationStage.ANALYZED,
        }

    async def _node_calculate_risk(self, state: InvestigationState) -> dict[str, Any]:
        """Evaluate financial exposure, expected cost, and LLM escalation conditions."""
        transactions = [Transaction(**t) for t in state.transactions]
        decision = DecisionResult(**state.decision) if state.decision else None
        category = ExceptionCategory(state.classified_category)
        confidence = Decimal(state.deterministic_confidence)

        exposure = ExposureCalculator.calculate_exposure(transactions)
        should_escalate, _ = ExposureCalculator.should_escalate_to_llm(
            financial_exposure=exposure,
            category=category,
            deterministic_confidence=confidence,
            is_duplicate=state.is_duplicate,
            decision=decision,
        )

        risk_out = RiskCalculator.calculate(
            RiskInput(
                category=category,
                financial_exposure=exposure,
                confidence=confidence,
                is_duplicate=state.is_duplicate,
            )
        )

        return {
            "financial_exposure": str(exposure),
            "expected_cost": str(risk_out.expected_cost),
            "risk_bucket": risk_out.risk_bucket.value,
            "requires_llm": should_escalate,
            "stage": InvestigationStage.RISK_EVALUATED,
        }

    async def _node_retrieve_history(self, state: InvestigationState) -> dict[str, Any]:
        """Retrieve relevant past exception patterns from Qdrant."""
        category = ExceptionCategory(state.classified_category)
        exposure = Decimal(state.financial_exposure)

        try:
            cases = await self.retriever.retrieve(
                category=category,
                exposure=exposure,
                evidence_summary=state.transaction_evidence,
                limit=5,
            )
            return {
                "historical_cases": cases,
                "stage": InvestigationStage.HISTORY_RETRIEVED,
            }
        except Exception as e:
            logger.warning(f"Historical retrieval failed gracefully: {e}")
            return {
                "historical_cases": [],
                "stage": InvestigationStage.HISTORY_RETRIEVED,
            }

    async def _node_llm_reasoning(self, state: InvestigationState) -> dict[str, Any]:
        """Perform selective LLM semantic reasoning on structured evidence."""
        context_payload = {
            "exception_id": state.exception_id,
            "category": state.classified_category,
            "financial_exposure": state.financial_exposure,
            "expected_cost": state.expected_cost,
            "evidence": state.transaction_evidence,
            "historical_cases": state.historical_cases,
            "preliminary_root_cause": state.root_cause,
        }

        try:
            llm_res = await self.llm_client.reason(context_payload)
            return {
                "llm_result": llm_res.model_dump(),
                "llm_invoked": True,
                "method": InvestigationMethod.LLM_ASSISTED.value,
                "stage": InvestigationStage.LLM_COMPLETE,
            }
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}. Falling back to deterministic analysis.")
            return {
                "llm_error": str(e),
                "llm_invoked": True,
                "method": InvestigationMethod.FALLBACK.value,
                "requires_human_review": True,
                "stage": InvestigationStage.LLM_COMPLETE,
            }

    async def _node_validate_llm_output(self, state: InvestigationState) -> dict[str, Any]:
        """Validate LLM output against schemas and financial invariants."""
        if not state.llm_result:
            return {
                "method": InvestigationMethod.FALLBACK.value,
                "requires_human_review": True,
                "stage": InvestigationStage.VALIDATED,
            }

        try:
            validated = LLMInvestigationResult(**state.llm_result)

            # Sanity bound: LLM reported exposure must not exceed 2x actual
            actual_exp = Decimal(state.financial_exposure)
            if validated.financial_exposure > (actual_exp * Decimal("2.0")):
                raise ValueError("LLM financial exposure exceeds sanity bound")

            return {
                "root_cause": validated.root_cause,
                "classified_category": validated.classification,
                "classification_confidence": str(validated.confidence),
                "recommended_action": validated.recommended_action.value,
                "requires_human_review": validated.requires_human_review,
                "explanation": validated.reasoning_summary,
                "method": InvestigationMethod.LLM_ASSISTED.value,
                "stage": InvestigationStage.VALIDATED,
            }
        except Exception as e:
            logger.error(f"LLM validation rejected output: {e}. Routing to fallback.")
            return {
                "llm_error": f"Validation failed: {e}",
                "method": InvestigationMethod.FALLBACK.value,
                "requires_human_review": True,
                "stage": InvestigationStage.VALIDATED,
            }

    async def _node_finalize_conclusion(self, state: InvestigationState) -> dict[str, Any]:
        """Package final InvestigationConclusion domain model."""
        confidence_str = (
            state.classification_confidence
            if state.classification_confidence != "0"
            else state.deterministic_confidence
        )

        conclusion = InvestigationConclusion(
            investigation_id=state.investigation_id,
            exception_id=state.exception_id,
            run_id=state.run_id,
            method=InvestigationMethod(state.method),
            root_cause=state.root_cause,
            classification=ExceptionCategory(state.classified_category),
            confidence=Decimal(confidence_str),
            financial_exposure=Decimal(state.financial_exposure),
            expected_cost=Decimal(state.expected_cost),
            recommended_action=state.recommended_action,
            requires_human_review=state.requires_human_review,
            evidence=state.transaction_evidence,
            llm_invoked=state.llm_invoked,
            llm_error=state.llm_error,
            historical_cases_used=len(state.historical_cases),
            status=InvestigationStatus.COMPLETED,
        )

        # Index completed investigation into retriever for future context
        try:
            await self.retriever.index_investigation(conclusion)
        except Exception as e:
            logger.warning(f"Could not index completed investigation: {e}")

        return {
            "final_conclusion": conclusion.model_dump(),
            "stage": InvestigationStage.COMPLETED,
        }

    # --- Router Functions ---

    def _route_after_risk(self, state: InvestigationState) -> str:
        if state.requires_llm:
            return "retrieve_history"
        return "finalize_conclusion"

    def _route_after_llm(self, state: InvestigationState) -> str:
        if state.llm_result is not None:
            return "validate_llm_output"
        return "finalize_conclusion"

    async def run(self, initial_state: InvestigationState) -> InvestigationConclusion:
        """Execute the LangGraph workflow and return the resulting InvestigationConclusion."""
        final_state_dict = await self.graph.ainvoke(initial_state)
        conclusion_dict = final_state_dict.get("final_conclusion")
        if not conclusion_dict:
            raise RuntimeError("Investigation workflow ended without producing a final conclusion.")
        return InvestigationConclusion(**conclusion_dict)
