"""
Unit tests for asynchronous Razorpay API Client.
"""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from app.integrations.razorpay.client import RazorpayClient
from app.integrations.razorpay.config import RazorpayConfig
from app.integrations.razorpay.exceptions import (
    RazorpayApiError,
    RazorpayAuthError,
    RazorpayConfigError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
)


@pytest.mark.asyncio
async def test_client_unconfigured_error():
    config = RazorpayConfig(key_id="", key_secret="")
    client = RazorpayClient(config=config)
    with pytest.raises(RazorpayConfigError):
        await client.fetch_payments()


@pytest.mark.asyncio
async def test_client_fetch_payments_success():
    config = RazorpayConfig(key_id="rzp_test_key", key_secret="rzp_test_secret")
    client = RazorpayClient(config=config)

    mock_resp = httpx.Response(
        status_code=200,
        json={"entity": "collection", "count": 1, "items": [{"id": "pay_test_01", "amount": 50000}]},
        request=httpx.Request("GET", "https://api.razorpay.com/v1/payments"),
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        res = await client.fetch_payments(count=10)
        assert res["count"] == 1
        assert res["items"][0]["id"] == "pay_test_01"


@pytest.mark.asyncio
async def test_client_auth_failure():
    config = RazorpayConfig(key_id="rzp_test_invalid", key_secret="bad_secret")
    client = RazorpayClient(config=config)

    mock_resp = httpx.Response(
        status_code=401,
        text='{"error":{"code":"BAD_REQUEST_ERROR","description":"Invalid Key or Auth Header"}}',
        request=httpx.Request("GET", "https://api.razorpay.com/v1/payments"),
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        with pytest.raises(RazorpayAuthError):
            await client.fetch_payments()


@pytest.mark.asyncio
async def test_client_not_found():
    config = RazorpayConfig(key_id="rzp_test_key", key_secret="rzp_test_secret")
    client = RazorpayClient(config=config)

    mock_resp = httpx.Response(
        status_code=404,
        text='{"error":{"description":"Payment not found"}}',
        request=httpx.Request("GET", "https://api.razorpay.com/v1/payments/pay_nonexistent"),
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        with pytest.raises(RazorpayNotFoundError):
            await client.fetch_payment_by_id("pay_nonexistent")


@pytest.mark.asyncio
async def test_client_multi_page_pagination():
    config = RazorpayConfig(key_id="rzp_test_key", key_secret="rzp_test_secret")
    client = RazorpayClient(config=config)

    # Page 1 returns 2 items; Page 2 returns 1 item
    page1 = httpx.Response(
        status_code=200,
        json={"entity": "collection", "count": 2, "items": [{"id": "pay_01"}, {"id": "pay_02"}]},
        request=httpx.Request("GET", "https://api.razorpay.com/v1/payments"),
    )
    page2 = httpx.Response(
        status_code=200,
        json={"entity": "collection", "count": 1, "items": [{"id": "pay_03"}]},
        request=httpx.Request("GET", "https://api.razorpay.com/v1/payments"),
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = [page1, page2]
        items = await client.fetch_paginated_entities(endpoint="/payments", limit=5, batch_size=2)
        assert len(items) == 3
        assert [item["id"] for item in items] == ["pay_01", "pay_02", "pay_03"]


@pytest.mark.asyncio
async def test_client_timeout_handling():
    config = RazorpayConfig(key_id="rzp_test_key", key_secret="rzp_test_secret")
    client = RazorpayClient(config=config, max_retries=1)

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = httpx.ReadTimeout("Request timed out")
        with pytest.raises(RazorpayApiError) as exc_info:
            await client.fetch_payments()
        assert "connection failed" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()
