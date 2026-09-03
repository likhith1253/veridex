"""
Razorpay Configuration Manager for Project Sentinel.

Securely handles environment variables for Razorpay Test Mode and Webhook authentication.
Ensures sensitive secrets (KEY_SECRET, WEBHOOK_SECRET) are never leaked to logs, APIs, or UI.
"""

import os
from typing import Any, Optional

from dotenv import load_dotenv
load_dotenv()


class RazorpayConfig:
    """Razorpay configuration provider with safe metadata extraction."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        mode: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._key_id = (key_id if key_id is not None else os.getenv("RAZORPAY_KEY_ID", "")).strip()
        self._key_secret = (key_secret if key_secret is not None else os.getenv("RAZORPAY_KEY_SECRET", "")).strip()
        self._webhook_secret = (webhook_secret if webhook_secret is not None else os.getenv("RAZORPAY_WEBHOOK_SECRET", "")).strip()
        self._mode = (mode if mode is not None else os.getenv("RAZORPAY_MODE", "test")).lower().strip()
        self._base_url = (base_url if base_url is not None else os.getenv("RAZORPAY_BASE_URL", "https://api.razorpay.com/v1")).rstrip("/")

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def key_secret(self) -> str:
        return self._key_secret

    @property
    def webhook_secret(self) -> str:
        return self._webhook_secret

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def is_configured(self) -> bool:
        """Check if minimum API credentials are present."""
        return bool(self._key_id and self._key_secret)

    @property
    def is_webhook_configured(self) -> bool:
        """Check if webhook secret is configured."""
        return bool(self._webhook_secret)

    @property
    def key_id_prefix(self) -> str:
        """Safe non-secret prefix for UI / status display (e.g. 'rzp_test_...')."""
        if not self._key_id:
            return ""
        if len(self._key_id) <= 8:
            return self._key_id[:4] + "..."
        return self._key_id[:8] + "..."

    def get_safe_status(self) -> dict[str, Any]:
        """Return safe metadata for frontend and status endpoints without leaking secrets."""
        return {
            "configured": self.is_configured,
            "mode": self._mode,
            "key_id_prefix": self.key_id_prefix,
            "webhook_configured": self.is_webhook_configured,
            "base_url": self._base_url,
        }


# Global default configuration instance
razorpay_config = RazorpayConfig()
