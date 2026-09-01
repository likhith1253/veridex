"""
Centralized Frontend API Client for Project Sentinel.

Communicates with the frozen FastAPI backend REST endpoints:
- Handles base URL configuration from environment
- Typed request/response mapping
- Graceful error handling, connection retries, and status reporting
"""

import os
from typing import Any, Optional
import httpx


class FinanceControllerAPIClient:
    """Client for the Project Sentinel Backend REST API."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 15.0):
        self.base_url = (base_url or os.getenv("SENTINEL_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def check_health(self) -> dict[str, Any]:
        """Check backend health status."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(self._url("/health"))
                res.raise_for_status()
                return {"status": "healthy", "data": res.json()}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    # --- Executive & Reconciliation ---
    def get_summary(self, run_id: Optional[str] = None) -> dict[str, Any]:
        params = {"run_id": run_id} if run_id else {}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/summary"), params=params)
            res.raise_for_status()
            return res.json()

    def list_runs(self, limit: int = 20) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/runs"), params={"limit": limit})
            res.raise_for_status()
            return res.json()

    def get_funnel(self, run_id: Optional[str] = None) -> dict[str, Any]:
        params = {"run_id": run_id} if run_id else {}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/funnel"), params=params)
            res.raise_for_status()
            return res.json()

    def get_exposure(self, run_id: Optional[str] = None) -> dict[str, Any]:
        params = {"run_id": run_id} if run_id else {}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/exposure"), params=params)
            res.raise_for_status()
            return res.json()

    def list_transactions(self, run_id: Optional[str] = None, limit: int = 100) -> dict[str, Any]:
        params = {"limit": limit}
        if run_id:
            params["run_id"] = run_id
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/transactions"), params=params)
            res.raise_for_status()
            return res.json()

    # --- Exception Management ---
    def list_exceptions(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        min_exposure: Optional[float] = None,
        max_exposure: Optional[float] = None,
        transaction_id: Optional[str] = None,
        run_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if category:
            params["category"] = category
        if min_exposure is not None:
            params["min_exposure"] = min_exposure
        if max_exposure is not None:
            params["max_exposure"] = max_exposure
        if transaction_id:
            params["transaction_id"] = transaction_id
        if run_id:
            params["run_id"] = run_id

        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/exceptions"), params=params)
            res.raise_for_status()
            return res.json()

    def get_exception_detail(self, exception_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url(f"/api/v1/controller/exceptions/{exception_id}"))
            res.raise_for_status()
            return res.json()

    def get_exception_aging(self, run_id: Optional[str] = None) -> dict[str, Any]:
        params = {"run_id": run_id} if run_id else {}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/exceptions/aging"), params=params)
            res.raise_for_status()
            return res.json()

    def get_exception_intelligence(self, exception_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url(f"/api/v1/controller/exceptions/{exception_id}/intelligence"))
            res.raise_for_status()
            return res.json()

    def get_exception_investigation_view(self, exception_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url(f"/api/v1/controller/exceptions/{exception_id}/investigation"))
            res.raise_for_status()
            return res.json()

    def list_exception_intelligence(self, run_id: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        params = {"limit": limit}
        if run_id:
            params["run_id"] = run_id
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/exceptions/intelligence"), params=params)
            res.raise_for_status()
            return res.json()

    # --- Human Decisions & Actions ---
    def apply_decision(
        self, exception_id: str, action: str, actor: str = "finance_controller_user", reason: Optional[str] = None
    ) -> dict[str, Any]:
        payload = {"action": action, "actor": actor, "reason": reason}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self._url(f"/api/v1/controller/exceptions/{exception_id}/decision"), json=payload)
            res.raise_for_status()
            return res.json()

    def assign_exception(self, exception_id: str, assigned_to: str, actor: str = "finance_controller_admin") -> dict[str, Any]:
        payload = {"assigned_to": assigned_to, "actor": actor}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self._url(f"/api/v1/controller/exceptions/{exception_id}/assign"), json=payload)
            res.raise_for_status()
            return res.json()

    def add_exception_note(self, exception_id: str, note: str, actor: str = "finance_controller_user") -> dict[str, Any]:
        payload = {"note": note, "actor": actor}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self._url(f"/api/v1/controller/exceptions/{exception_id}/note"), json=payload)
            res.raise_for_status()
            return res.json()

    # --- Accounting & Treasury ---
    def get_settlement_accounting(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/settlement/accounting"))
            res.raise_for_status()
            return res.json()

    def get_refund_audit(self, limit: int = 100) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/refunds/audit"), params={"limit": limit})
            res.raise_for_status()
            return res.json()

    def get_duplicate_audit(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/duplicates/audit"))
            res.raise_for_status()
            return res.json()

    def get_fee_tax_control(self, limit: int = 100) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/fee-tax-control"), params={"limit": limit})
            res.raise_for_status()
            return res.json()

    def get_cash_position(self, run_id: Optional[str] = None) -> dict[str, Any]:
        params = {"run_id": run_id} if run_id else {}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/cash-position"), params=params)
            res.raise_for_status()
            return res.json()

    def get_forecast(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/forecast"))
            res.raise_for_status()
            return res.json()

    def get_source_health(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/source-health"))
            res.raise_for_status()
            return res.json()

    def get_benchmark(self, num_transactions: int = 100, seed: int = 42) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/benchmark"), params={"num_transactions": num_transactions, "seed": seed})
            res.raise_for_status()
            return res.json()

    # --- Intelligence & Audit ---
    def ask_qa(self, question: str, run_id: Optional[str] = None) -> dict[str, Any]:
        payload = {"question": question, "run_id": run_id}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self._url("/api/v1/controller/qa"), json=payload)
            res.raise_for_status()
            return res.json()

    def ask_copilot(self, question: str, run_id: Optional[str] = None) -> dict[str, Any]:
        payload = {"question": question, "run_id": run_id}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self._url("/api/v1/controller/copilot/query"), json=payload)
            res.raise_for_status()
            return res.json()

    def get_daily_brief(self, run_id: Optional[str] = None) -> dict[str, Any]:
        payload = {"run_id": run_id} if run_id else {}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self._url("/api/v1/controller/copilot/brief"), json=payload)
            res.raise_for_status()
            return res.json()

    def get_audit_timeline(self, run_id: Optional[str] = None, transaction_id: Optional[str] = None) -> list[dict[str, Any]]:
        params = {}
        if run_id:
            params["run_id"] = run_id
        if transaction_id:
            params["transaction_id"] = transaction_id
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(self._url("/api/v1/controller/audit/timeline"), params=params)
            res.raise_for_status()
            return res.json()

    # --- Ingestion & Simulation ---
    def simulate_failure(self, scenario: str, amount: float = 50000.0) -> dict[str, Any]:
        payload = {"scenario": scenario, "amount": amount}
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self._url("/api/v1/controller/simulate-failure"), json=payload)
            res.raise_for_status()
            return res.json()
