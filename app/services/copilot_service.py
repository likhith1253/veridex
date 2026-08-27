"""Grounded finance copilot built on top of Sentinel's existing controller and intelligence services."""

from __future__ import annotations

from typing import Any, Optional

from app.services.finance_controller import FinanceController
from app.services.finance_qa import FinanceQAService
from app.services.source_health_service import SourceHealthService


class FinanceCopilotService:
    """Deterministic finance copilot that answers controller questions using real data."""

    @staticmethod
    def suggested_questions() -> list[str]:
        return [
            "What needs my attention right now?",
            "Where is the highest monetary exposure?",
            "Why are these transactions unresolved?",
            "Show me the highest-risk exception.",
            "Which source is unhealthy?",
            "What can I safely auto-resolve?",
            "What requires human review?",
            "Explain today's reconciliation performance.",
            "What changed since the last reconciliation run?",
            "Why was this exception created?",
            "What evidence supports this exception?",
            "What is the financial impact of this exception?",
            "What should I do with this exception?",
            "Does this exception require human review?",
            "Explain the matching failure for this exception.",
        ]

    def __init__(self, session, llm_client: Optional[Any] = None):
        self.session = session
        self.qa_service = FinanceQAService(session, llm_client=llm_client)

    async def _gather_context(self, run_id: Optional[str] = None) -> dict[str, Any]:
        controller = FinanceController(self.session)
        summary = await controller.get_summary_kpis(run_id)
        summary_dict = summary.to_dict()

        source_health = await SourceHealthService(self.session).get_source_health()
        exceptions_payload, _ = await controller.exc_mgmt_service.list_exceptions(run_id=run_id, page_size=10)
        intelligence = await controller.list_exception_intelligence(run_id=run_id, limit=10)

        top_exception = None
        if intelligence:
            top_exception = intelligence[0]
        elif exceptions_payload:
            top_exception = exceptions_payload[0]

        return {
            "summary": summary_dict,
            "exceptions": exceptions_payload,
            "intelligence": intelligence,
            "top_exception": top_exception,
            "source_health": source_health.to_dict(),
        }

    @staticmethod
    def _status_for(summary: dict[str, Any], health: dict[str, Any]) -> str:
        unresolved = float(summary.get("unresolved_monetary_exposure_inr", 0.0) or 0.0)
        match_rate = float(summary.get("match_rate", 0.0) or 0.0)
        overall_health = str(health.get("overall_health", "HEALTHY")).upper()

        if unresolved > 250000 or overall_health != "HEALTHY" or match_rate < 75:
            return "Critical"
        if unresolved > 100000 or overall_health == "DEGRADED" or match_rate < 85:
            return "Attention Required"
        return "Stable"

    @staticmethod
    def _human_review_required(summary: dict[str, Any], top_exception: Optional[dict[str, Any]], health: dict[str, Any]) -> bool:
        if not top_exception:
            return False
        risk_bucket = str(top_exception.get("risk_bucket", "")).lower()
        unresolved = float(summary.get("unresolved_monetary_exposure_inr", 0.0) or 0.0)
        overall_health = str(health.get("overall_health", "HEALTHY")).upper()
        return risk_bucket in {"high", "critical"} or unresolved > 100000 or overall_health != "HEALTHY"

    async def generate_daily_brief(self, run_id: Optional[str] = None) -> dict[str, Any]:
        context = await self._gather_context(run_id)
        summary = context["summary"]
        health = context["source_health"]
        top_exception = context["top_exception"]

        risk_exception = top_exception or {}
        money_at_risk = float(summary.get("unresolved_monetary_exposure_inr", 0.0) or 0.0)
        match_rate = float(summary.get("match_rate", 0.0) or 0.0)
        status = self._status_for(summary, health)
        human_review = self._human_review_required(summary, top_exception, health)

        explanation = "No open exception with a material financial impact was found in the current scope."
        if top_exception:
            explanation = top_exception.get("why_it_happened") or top_exception.get("root_cause") or top_exception.get("explanation") or explanation

        recommended_action = "Monitor the exception queue and schedule a human review in the next controller cycle."
        if top_exception:
            recommended_action = top_exception.get("recommended_action") or top_exception.get("next_steps", [recommended_action])[0]
            if isinstance(recommended_action, list):
                recommended_action = recommended_action[0]

        evidence = []
        if top_exception:
            evidence.append({
                "exception_id": top_exception.get("exception_id"),
                "transaction_id": top_exception.get("transaction_id"),
                "category": top_exception.get("category"),
                "risk_bucket": top_exception.get("risk_bucket"),
                "financial_exposure_inr": top_exception.get("financial_exposure_inr"),
                "recommended_action": top_exception.get("recommended_action"),
            })
            if health.get("sources"):
                evidence.append({
                    "source_health": health.get("overall_health"),
                    "sources": health.get("sources", {}),
                })
        else:
            evidence = [{"source_health": health.get("overall_health"), "sources": health.get("sources", {})}]

        return {
            "status": status,
            "money_at_risk_inr": money_at_risk,
            "reconciliation_match_rate_percent": match_rate,
            "highest_risk_exception": risk_exception.get("exception_id"),
            "why": explanation,
            "recommended_action": recommended_action,
            "human_review_required": human_review,
            "evidence": evidence if isinstance(evidence, list) else [evidence] if evidence else [],
            "source_health": health.get("overall_health", "HEALTHY"),
            "summary": summary,
        }

    async def answer_question(self, question: str, run_id: Optional[str] = None) -> dict[str, Any]:
        q = (question or "").strip()
        if not q:
            raise ValueError("Question must not be empty.")

        q_lower = q.lower()
        context = await self._gather_context(run_id)
        summary = context["summary"]

        if any(term in q_lower for term in [
            "what needs my attention right now",
            "attention first",
            "highest risk",
            "highest-risk",
            "which exception",
            "priority",
            "biggest issue",
            "biggest risk",
            "highest monetary exposure",
            "what needs attention",
            "show me the highest-risk exception",
        ]):
            priority_exception = context["top_exception"] or (context["intelligence"][0] if context["intelligence"] else None)
            if not priority_exception:
                return {
                    "question": q,
                    "answer": "There are currently no open exceptions in the selected controller scope.",
                    "interpretation": "No exception drift is active for this scope.",
                    "recommendation": "Review the live exception queue later if new mismatches appear.",
                    "fact_summary": {"highest_risk_exception_id": None, "unresolved_exposure_inr": summary.get("unresolved_monetary_exposure_inr", 0.0)},
                    "evidence": [],
                    "source": "deterministic",
                    "needs_human_review": False,
                }

            amount = float(priority_exception.get("financial_exposure_inr", priority_exception.get("financial_exposure", 0.0)))
            action = priority_exception.get("recommended_action") or priority_exception.get("next_steps", ["escalate_manual"])[0]
            answer = (
                f"The highest-priority exception is {priority_exception.get('exception_id')} with a "
                f"{priority_exception.get('risk_bucket', 'unknown').upper()} risk profile and INR {amount:,.2f} in exposure."
            )
            interpretation = (
                f"This exception is the most material issue in the current controller scope, and it is worth immediate review because "
                f"the unresolved exposure remains high relative to the current exception load."
            )
            recommendation = action if action else "escalate_manual"
            return {
                "question": q,
                "answer": answer,
                "interpretation": interpretation,
                "recommendation": recommendation,
                "fact_summary": {
                    "highest_risk_exception_id": priority_exception.get("exception_id"),
                    "highest_risk_amount_inr": amount,
                    "overall_unresolved_exposure_inr": summary.get("unresolved_monetary_exposure_inr", 0.0),
                    "match_rate_percent": summary.get("match_rate", 0.0),
                    "overall_health": context["source_health"].get("overall_health", "HEALTHY"),
                },
                "evidence": [priority_exception] if isinstance(priority_exception, dict) else [priority_exception] if priority_exception else [],
                "source": "deterministic",
                "needs_human_review": priority_exception.get("risk_bucket") in {"high", "critical"},
            }

        if any(term in q_lower for term in ["source health", "feed health", "gateway", "ledger", "bank", "data quality", "which source is unhealthy"]):
            health = context["source_health"]
            overall_health = health.get("overall_health", "HEALTHY")
            sources = health.get("sources", {})
            degraded = []
            for source_name, source_data in sources.items():
                if source_data.get("health_status", "HEALTHY") != "HEALTHY":
                    degraded.append({"source": source_name, "status": source_data.get("health_status"), "exception_rate_percent": source_data.get("exception_rate_percent")})

            answer = f"The current feed health is {overall_health}."
            if degraded:
                answer += " The highest-risk source is currently " + degraded[0]["source"] + "."
            else:
                answer += " No feed is currently in a degraded state."
            return {
                "question": q,
                "answer": answer,
                "interpretation": "This is a feed-quality view of the data pipeline rather than a reconciliation outcome.",
                "recommendation": "Check the degraded feed for throughput, duplicate records, or settlement delays before the next reconciliation window.",
                "fact_summary": {"overall_health": overall_health, "degraded_sources": degraded},
                "evidence": degraded or [{"source": "all_feeds", "status": overall_health}],
                "source": "deterministic",
                "needs_human_review": overall_health != "HEALTHY",
            }

        if any(term in q_lower for term in ["auto-resolve", "safely auto", "automated", "auto resolve", "can i safely"]):
            top_exception = context["top_exception"]
            action = "review" if top_exception else "monitor"
            if top_exception:
                action = top_exception.get("recommended_action") or "review"
            return {
                "question": q,
                "answer": "The controller can safely automate only low-risk, low-ambiguity cases that already match the deterministic policy.",
                "interpretation": "This is a confidence and policy boundary assessment, not a database mutation action.",
                "recommendation": f"Treat {action} as the safe next operational action while leaving high-value or ambiguous exceptions for a human reviewer.",
                "fact_summary": {"safe_action": action, "requires_human_review": self._human_review_required(summary, top_exception, context["source_health"])},
                "evidence": [top_exception] if top_exception else [{"scope": "controller_policy", "safe_action": action}],
                "source": "deterministic",
                "needs_human_review": self._human_review_required(summary, top_exception, context["source_health"]),
            }

        if any(term in q_lower for term in ["human review", "requires human review", "what requires human review", "human approval"]):
            needs_review = self._human_review_required(summary, context["top_exception"], context["source_health"])
            return {
                "question": q,
                "answer": "Human review is required." if needs_review else "Human review is not currently required for the highest-priority issue in this scope.",
                "interpretation": "The decision boundary is based on risk bucket, unresolved exposure, and live source health."
                ,
                "recommendation": "Keep the exception queue in review while the controller highlights unresolved and high-risk items.",
                "fact_summary": {
                    "requires_human_review": needs_review,
                    "overall_health": context["source_health"].get("overall_health", "HEALTHY"),
                    "unresolved_exposure_inr": summary.get("unresolved_monetary_exposure_inr", 0.0),
                },
                "evidence": [context["top_exception"]] if context["top_exception"] else [{"source_health": context["source_health"].get("overall_health", "HEALTHY")}],
                "source": "deterministic",
                "needs_human_review": needs_review,
            }

        # Investigation-aware questions
        if any(term in q_lower for term in ["why was this exception created", "why this exception", "exception created"]):
            top_exception = context["top_exception"]
            if not top_exception:
                return {
                    "question": q,
                    "answer": "There are no exceptions in the current scope to investigate.",
                    "interpretation": "No exception records exist for this reconciliation run.",
                    "recommendation": "Check if any exceptions have been created by running a reconciliation.",
                    "fact_summary": {"exception_count": 0},
                    "evidence": [],
                    "source": "deterministic",
                    "needs_human_review": False,
                }
            
            return {
                "question": q,
                "answer": f"Exception {top_exception.get('exception_id')} was created due to: {top_exception.get('why_it_happened', top_exception.get('root_cause', top_exception.get('explanation', 'Unknown cause')))}",
                "interpretation": "This exception was flagged by the reconciliation system based on matching evidence and risk assessment.",
                "recommendation": top_exception.get("recommended_action") or "Review the exception evidence and matching details.",
                "fact_summary": {
                    "exception_id": top_exception.get("exception_id"),
                    "category": top_exception.get("category"),
                    "risk_bucket": top_exception.get("risk_bucket"),
                    "financial_exposure_inr": top_exception.get("financial_exposure_inr"),
                },
                "evidence": [top_exception] if isinstance(top_exception, dict) else [top_exception] if top_exception else [],
                "source": "deterministic",
                "needs_human_review": top_exception.get("risk_bucket") in {"high", "critical"},
            }

        if any(term in q_lower for term in ["what evidence supports this exception", "evidence supports", "matching evidence"]):
            top_exception = context["top_exception"]
            if not top_exception:
                return {
                    "question": q,
                    "answer": "There are no exceptions in the current scope to examine evidence for.",
                    "interpretation": "No exception records exist for this reconciliation run.",
                    "recommendation": "Run a reconciliation to generate exception records with evidence.",
                    "fact_summary": {"exception_count": 0},
                    "evidence": [],
                    "source": "deterministic",
                    "needs_human_review": False,
                }
            
            supporting_facts = top_exception.get("what_evidence_supports_this", [])
            evidence_summary = ", ".join([f"{f.get('label')}: {f.get('value')}" for f in supporting_facts[:5]])
            
            return {
                "question": q,
                "answer": f"The supporting evidence includes: {evidence_summary if evidence_summary else 'No structured evidence available'}",
                "interpretation": "This evidence comes from the matching process, investigation results, and risk assessment.",
                "recommendation": "Review the full investigation view for detailed matching evidence and mismatched fields.",
                "fact_summary": {
                    "exception_id": top_exception.get("exception_id"),
                    "evidence_count": len(supporting_facts),
                    "confidence": top_exception.get("confidence", 0),
                },
                "evidence": supporting_facts,
                "source": "deterministic",
                "needs_human_review": top_exception.get("risk_bucket") in {"high", "critical"},
            }

        if any(term in q_lower for term in ["what is the financial impact", "financial impact of this exception", "monetary impact"]):
            top_exception = context["top_exception"]
            if not top_exception:
                return {
                    "question": q,
                    "answer": "There are no exceptions in the current scope to assess financial impact.",
                    "interpretation": "No exception records exist for this reconciliation run.",
                    "recommendation": "Run a reconciliation to generate exception records with financial exposure data.",
                    "fact_summary": {"exception_count": 0},
                    "evidence": [],
                    "source": "deterministic",
                    "needs_human_review": False,
                }
            
            exposure = top_exception.get("financial_exposure_inr", top_exception.get("financial_exposure", 0))
            expected_cost = top_exception.get("how_serious", {}).get("expected_cost_inr", 0)
            
            return {
                "question": q,
                "answer": f"The financial impact is ₹{exposure:,.2f} in exposure with an expected cost of ₹{expected_cost:,.2f}.",
                "interpretation": "This represents the monetary value at risk due to this exception.",
                "recommendation": "Prioritize resolution based on the exposure amount and risk bucket.",
                "fact_summary": {
                    "exception_id": top_exception.get("exception_id"),
                    "financial_exposure_inr": exposure,
                    "expected_cost_inr": expected_cost,
                    "risk_bucket": top_exception.get("risk_bucket"),
                },
                "evidence": [top_exception] if isinstance(top_exception, dict) else [top_exception] if top_exception else [],
                "source": "deterministic",
                "needs_human_review": top_exception.get("risk_bucket") in {"high", "critical"} or exposure > 100000,
            }

        if any(term in q_lower for term in ["what should i do with this exception", "what should i do", "recommended action", "next steps"]):
            top_exception = context["top_exception"]
            if not top_exception:
                return {
                    "question": q,
                    "answer": "There are no exceptions in the current scope requiring action.",
                    "interpretation": "No exception records exist for this reconciliation run.",
                    "recommendation": "Monitor the exception queue for new items after reconciliation runs.",
                    "fact_summary": {"exception_count": 0},
                    "evidence": [],
                    "source": "deterministic",
                    "needs_human_review": False,
                }
            
            next_steps = top_exception.get("what_should_the_operator_do_next", [])
            recommended_action = top_exception.get("recommended_action", "review_exception")
            
            if isinstance(next_steps, list) and next_steps:
                action_summary = "; ".join(next_steps[:3])
            else:
                action_summary = recommended_action
            
            return {
                "question": q,
                "answer": f"Recommended action: {action_summary}",
                "interpretation": "This recommendation is based on the exception category, risk assessment, and financial exposure.",
                "recommendation": action_summary,
                "fact_summary": {
                    "exception_id": top_exception.get("exception_id"),
                    "recommended_action": recommended_action,
                    "risk_bucket": top_exception.get("risk_bucket"),
                    "requires_human_review": top_exception.get("risk_bucket") in {"high", "critical"},
                },
                "evidence": [top_exception] if isinstance(top_exception, dict) else [top_exception] if top_exception else [],
                "source": "deterministic",
                "needs_human_review": top_exception.get("risk_bucket") in {"high", "critical"},
            }

        if any(term in q_lower for term in ["does this exception require human review", "require human review", "human review needed"]):
            top_exception = context["top_exception"]
            if not top_exception:
                return {
                    "question": q,
                    "answer": "There are no exceptions in the current scope to assess.",
                    "interpretation": "No exception records exist for this reconciliation run.",
                    "recommendation": "Run a reconciliation to generate exception records.",
                    "fact_summary": {"exception_count": 0},
                    "evidence": [],
                    "source": "deterministic",
                    "needs_human_review": False,
                }
            
            risk_bucket = top_exception.get("risk_bucket", "unknown").lower()
            requires_review = risk_bucket in {"high", "critical"}
            exposure = top_exception.get("financial_exposure_inr", top_exception.get("financial_exposure", 0))
            
            if requires_review or exposure > 100000:
                answer = f"Yes, this exception requires human review due to {risk_bucket.upper()} risk profile and ₹{exposure:,.2f} exposure."
            else:
                answer = f"This exception does not require immediate human review based on its {risk_bucket.upper()} risk profile and ₹{exposure:,.2f} exposure."
            
            return {
                "question": q,
                "answer": answer,
                "interpretation": "Human review requirements are determined by risk bucket, financial exposure, and decision boundary policy.",
                "recommendation": "Proceed with the recommended action if no human review is required, otherwise escalate to a finance controller.",
                "fact_summary": {
                    "exception_id": top_exception.get("exception_id"),
                    "risk_bucket": top_exception.get("risk_bucket"),
                    "financial_exposure_inr": exposure,
                    "requires_human_review": requires_review or exposure > 100000,
                },
                "evidence": [top_exception] if isinstance(top_exception, dict) else [top_exception] if top_exception else [],
                "source": "deterministic",
                "needs_human_review": requires_review or exposure > 100000,
            }

        if any(term in q_lower for term in ["explain the matching failure", "matching failure", "why did matching fail"]):
            top_exception = context["top_exception"]
            if not top_exception:
                return {
                    "question": q,
                    "answer": "There are no exceptions in the current scope to analyze matching failures.",
                    "interpretation": "No exception records exist for this reconciliation run.",
                    "recommendation": "Run a reconciliation to generate exception records with matching evidence.",
                    "fact_summary": {"exception_count": 0},
                    "evidence": [],
                    "source": "deterministic",
                    "needs_human_review": False,
                }
            
            root_cause = top_exception.get("why_it_happened", top_exception.get("root_cause", top_exception.get("explanation", "Unknown")))
            category = top_exception.get("category", "unknown")
            
            return {
                "question": q,
                "answer": f"Matching failed due to {category}: {root_cause}",
                "interpretation": "The matching process could not establish a confident link between transaction records.",
                "recommendation": "Review the specific mismatched fields and candidate matches in the investigation view.",
                "fact_summary": {
                    "exception_id": top_exception.get("exception_id"),
                    "category": category,
                    "confidence": top_exception.get("confidence", 0),
                },
                "evidence": [top_exception] if isinstance(top_exception, dict) else [top_exception] if top_exception else [],
                "source": "deterministic",
                "needs_human_review": top_exception.get("risk_bucket") in {"high", "critical"},
            }

        qa_resp = await self.qa_service.answer_query(q, run_id)
        return {
            "question": q,
            "answer": qa_resp.direct_answer,
            "interpretation": qa_resp.direct_answer,
            "recommendation": "Validate the live exception list and confirm the working capital impact before closing this issue.",
            "fact_summary": qa_resp.key_metrics,
            "evidence": qa_resp.evidence_records if isinstance(qa_resp.evidence_records, list) else [qa_resp.evidence_records] if qa_resp.evidence_records else [],
            "source": "deterministic",
            "needs_human_review": False,
        }
