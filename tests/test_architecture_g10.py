import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import create_app
from app.services.finance_controller import FinanceController


def test_aud_007_benchmark_evaluation_static_method():
    """Verify FinanceController.get_benchmark_evaluation runs cleanly as a static method without __new__ hacks."""
    res = FinanceController.get_benchmark_evaluation(num_transactions=10, seed=42)
    assert isinstance(res, dict)
    assert res.get("scope") == "evaluation_only"
    assert res.get("benchmark", {}).get("num_transactions") == 10
    assert "result" in res
    assert "overall" in res["result"]
    assert "accuracy" in res["result"]["overall"]


@pytest.mark.asyncio
async def test_aud_007_benchmark_endpoint_live():
    """Verify GET /api/v1/controller/benchmark returns valid evaluation benchmark without instance corruption."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/controller/benchmark?num_transactions=10&seed=42")
        assert res.status_code == 200
        data = res.json()
        assert data.get("scope") == "evaluation_only"
        assert data.get("benchmark", {}).get("num_transactions") == 10
        assert "result" in data
