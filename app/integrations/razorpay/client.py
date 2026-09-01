"""
Asynchronous Razorpay API Client for Project Sentinel.

Implements secure HTTPS communication with Razorpay REST APIs:
- Basic Auth using KEY_ID and KEY_SECRET
- Strict timeouts, connection pooling, and bounded exponential retries
- Transparent error mapping (Auth, RateLimit, NotFound, ApiError)
- Redacted logging (never logs credentials or authorization headers)
"""

import asyncio
import logging
from typing import Any, Optional
import httpx

from app.integrations.razorpay.config import RazorpayConfig, razorpay_config
from app.integrations.razorpay.exceptions import (
    RazorpayApiError,
    RazorpayAuthError,
    RazorpayConfigError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
)

logger = logging.getLogger(__name__)


class RazorpayClient:
    """Async client for interacting with Razorpay REST endpoints."""

    def __init__(
        self,
        config: Optional[RazorpayConfig] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.config = config or razorpay_config
        self.timeout = timeout
        self.max_retries = max_retries

    def _get_auth(self) -> tuple[str, str]:
        if not self.config.is_configured:
            raise RazorpayConfigError("Razorpay credentials (KEY_ID, KEY_SECRET) are not configured.")
        return (self.config.key_id, self.config.key_secret)

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute an authenticated HTTP request with retries and structured error handling."""
        auth = self._get_auth()
        url = f"{self.config.base_url}{path}"
        headers = {"User-Agent": "Project-Sentinel-Finance-Controller/1.0"}

        last_exception: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        auth=auth,
                        params=params,
                        json=json_data,
                        headers=headers,
                    )

                    # 1. Success response
                    if response.status_code in (200, 201):
                        return response.json()

                    # 2. Authentication failure
                    if response.status_code in (401, 403):
                        logger.warning("Razorpay auth rejected for %s (HTTP %d)", path, response.status_code)
                        raise RazorpayAuthError(
                            message=f"Razorpay authentication failed: {response.text}",
                            status_code=response.status_code,
                        )

                    # 3. Rate limiting
                    if response.status_code == 429:
                        logger.warning("Razorpay rate limit exceeded on %s (attempt %d/%d)", path, attempt, self.max_retries)
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (2 ** attempt))
                            continue
                        raise RazorpayRateLimitError("Razorpay API rate limit exceeded.", status_code=429)

                    # 4. Resource Not Found
                    if response.status_code == 404:
                        raise RazorpayNotFoundError(f"Razorpay resource not found at {path}", status_code=404)

                    # 5. Server error (5xx) -> Retryable
                    if response.status_code >= 500:
                        logger.warning("Razorpay server error %d on %s (attempt %d/%d)", response.status_code, path, attempt, self.max_retries)
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (2 ** attempt))
                            continue
                        raise RazorpayApiError(f"Razorpay server error: HTTP {response.status_code}", status_code=response.status_code)

                    # 6. Other 4xx client errors
                    raise RazorpayApiError(
                        message=f"Razorpay API request failed (HTTP {response.status_code}): {response.text}",
                        status_code=response.status_code,
                    )

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
                last_exception = exc
                logger.warning("Razorpay connection issue on %s (attempt %d/%d): %s", path, attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                raise RazorpayApiError(f"Razorpay connection failed after {self.max_retries} attempts: {exc}")

        if last_exception:
            raise RazorpayApiError(f"Razorpay request failed: {last_exception}")
        raise RazorpayApiError("Unknown Razorpay request failure.")

    async def check_connectivity(self) -> bool:
        """Check if Razorpay API is reachable with configured credentials."""
        if not self.config.is_configured:
            return False
        try:
            # Lightweight ping via payments endpoint with limit=1
            await self.fetch_payments(count=1)
            return True
        except Exception as e:
            logger.info("Razorpay connectivity check returned: %s", e)
            return False

    async def fetch_payments(
        self,
        count: int = 100,
        skip: int = 0,
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> dict[str, Any]:
        """Retrieve list of payments from Razorpay."""
        params: dict[str, Any] = {"count": count, "skip": skip}
        if from_ts:
            params["from"] = from_ts
        if to_ts:
            params["to"] = to_ts
        return await self._request("GET", "/payments", params=params)

    async def fetch_payment_by_id(self, payment_id: str) -> dict[str, Any]:
        """Retrieve single payment details by ID."""
        return await self._request("GET", f"/payments/{payment_id}")

    async def fetch_orders(
        self,
        count: int = 100,
        skip: int = 0,
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> dict[str, Any]:
        """Retrieve list of orders from Razorpay."""
        params: dict[str, Any] = {"count": count, "skip": skip}
        if from_ts:
            params["from"] = from_ts
        if to_ts:
            params["to"] = to_ts
        return await self._request("GET", "/orders", params=params)

    async def fetch_order_by_id(self, order_id: str) -> dict[str, Any]:
        """Retrieve single order details by ID."""
        return await self._request("GET", f"/orders/{order_id}")

    async def fetch_settlements(
        self,
        count: int = 100,
        skip: int = 0,
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> dict[str, Any]:
        """Retrieve list of settlements from Razorpay."""
        params: dict[str, Any] = {"count": count, "skip": skip}
        if from_ts:
            params["from"] = from_ts
        if to_ts:
            params["to"] = to_ts
        return await self._request("GET", "/settlements", params=params)

    async def fetch_settlement_by_id(self, settlement_id: str) -> dict[str, Any]:
        """Retrieve single settlement details by ID."""
        return await self._request("GET", f"/settlements/{settlement_id}")

    async def fetch_combined_recon(
        self,
        year: int,
        month: int,
        day: int,
        count: int = 100,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Retrieve combined settlement reconciliation details for a given date."""
        params = {"year": year, "month": month, "day": day, "count": count, "skip": skip}
        return await self._request("GET", "/settlements/recon/combined", params=params)

    async def fetch_paginated_entities(
        self,
        endpoint: str,
        limit: int = 100,
        batch_size: int = 100,
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Iteratively fetch multiple pages of entities up to `limit` without infinite loops."""
        all_items: list[dict[str, Any]] = []
        skip = 0
        step = min(max(batch_size, 1), 100)
        max_pages = max(1, (limit // step) + 2)

        for _ in range(max_pages):
            if len(all_items) >= limit:
                break

            count_to_fetch = min(step, limit - len(all_items))
            params: dict[str, Any] = {"count": count_to_fetch, "skip": skip}
            if from_ts:
                params["from"] = from_ts
            if to_ts:
                params["to"] = to_ts

            res = await self._request("GET", endpoint, params=params)
            items = res.get("items", [])
            if not items and "entity" in res:
                items = [res]

            if not items:
                break

            all_items.extend(items)
            skip += len(items)

            if len(items) < count_to_fetch:
                break

        return all_items[:limit]

