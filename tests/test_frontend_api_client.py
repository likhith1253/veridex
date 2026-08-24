"""
Unit and Integration Tests for Frontend REST API Client and Dashboard Helpers.
"""

from unittest.mock import MagicMock, patch
import pytest
from ui.api_client import FinanceControllerAPIClient


class TestFrontendAPIClient:
    """Test UI REST API Client."""

    @patch("httpx.Client")
    def test_get_summary(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "total_records_processed": 150,
            "match_rate": 90.0,
            "f1_score": 94.74,
        }
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        client = FinanceControllerAPIClient()
        data = client.get_summary()

        assert data["total_records_processed"] == 150
        assert data["match_rate"] == 90.0

    @patch("httpx.Client")
    def test_apply_decision(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "exception_id": "exc-1",
            "action": "approve",
            "audit_event_id": "audit-1",
        }
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        client = FinanceControllerAPIClient()
        data = client.apply_decision("exc-1", "approve", "lead_analyst", "Confirmed match")

        assert data["action"] == "approve"
        assert data["audit_event_id"] == "audit-1"

    @patch("httpx.Client")
    def test_get_settlement_accounting(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "gross_gateway_volume": "100000.00",
            "expected_net_settlement": "97640.00",
            "settlement_reconciliation_status": "RECONCILED",
        }
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        client = FinanceControllerAPIClient()
        data = client.get_settlement_accounting()

        assert data["gross_gateway_volume"] == "100000.00"
        assert data["settlement_reconciliation_status"] == "RECONCILED"
