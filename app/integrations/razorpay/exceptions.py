"""
Razorpay Integration Exceptions for Project Sentinel.
"""

from typing import Optional


class RazorpayIntegrationError(Exception):
    """Base exception for Razorpay integration failures."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class RazorpayConfigError(RazorpayIntegrationError):
    """Raised when Razorpay credentials or required settings are missing."""
    pass


class RazorpayAuthError(RazorpayIntegrationError):
    """Raised when Razorpay API rejects authentication (HTTP 401/403)."""
    pass


class RazorpayRateLimitError(RazorpayIntegrationError):
    """Raised when Razorpay API rate limit is exceeded (HTTP 429)."""
    pass


class RazorpayApiError(RazorpayIntegrationError):
    """Raised when Razorpay API returns a server or domain error."""
    pass


class RazorpaySignatureError(RazorpayIntegrationError):
    """Raised when Webhook HMAC-SHA256 signature verification fails."""
    pass


class RazorpayNotFoundError(RazorpayIntegrationError):
    """Raised when a requested resource (payment, settlement, order) is not found."""
    pass
