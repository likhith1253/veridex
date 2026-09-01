"""
Unit tests for Razorpay Configuration and Secret Shielding.
"""

from app.integrations.razorpay.config import RazorpayConfig


def test_razorpay_config_defaults():
    config = RazorpayConfig(key_id="", key_secret="", webhook_secret="")
    assert config.is_configured is False
    assert config.is_webhook_configured is False
    assert config.key_id_prefix == ""
    assert config.mode == "test"

    safe_status = config.get_safe_status()
    assert safe_status["configured"] is False
    assert "key_secret" not in safe_status
    assert "webhook_secret" not in safe_status


def test_razorpay_config_with_credentials():
    config = RazorpayConfig(
        key_id="rzp_test_1234567890abcdef",
        key_secret="super_secret_key_value",
        webhook_secret="webhook_secret_key_value",
        mode="test",
    )
    assert config.is_configured is True
    assert config.is_webhook_configured is True
    assert config.key_id_prefix == "rzp_test..."
    assert config.mode == "test"

    safe_status = config.get_safe_status()
    assert safe_status["configured"] is True
    assert safe_status["webhook_configured"] is True
    assert safe_status["key_id_prefix"] == "rzp_test..."
    # Ensure raw secrets are NEVER exposed in status output
    assert "super_secret_key_value" not in str(safe_status)
    assert "webhook_secret_key_value" not in str(safe_status)
