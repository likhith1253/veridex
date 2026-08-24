"""End-to-end test for ReconciliationService with PostgreSQL integration."""
import os
from datetime import datetime
from decimal import Decimal

import pytest

from app.matching.decision import DecisionPolicy
from app.models.decision_result import DecisionAction
from app.models.reconciliation_summary import ReconciliationSummary
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.reconciliation import ReconciliationService


def test_no_csv_parsing_in_service():
    """Verify ReconciliationService does not parse CSVs."""
    import inspect
    import app.services.reconciliation as service_module
    
    source = inspect.getsource(service_module)
    
    # Check for CSV-related imports or operations
    assert "csv" not in source.lower()
    assert "pandas" not in source.lower()
    assert "read_csv" not in source.lower()
    assert ".csv" not in source.lower()


def test_ml_training_wired_in_service():
    """ML training is intentionally wired into _run_ml_scoring."""
    import inspect
    import app.services.reconciliation as service_module

    source = inspect.getsource(service_module)

    # ML is now intentionally active: .train( must be present in _run_ml_scoring
    assert ".train(" in source
    # No CSV parsing in service (unrelated data loading)
    assert "read_csv" not in source
    assert "TrainingData" not in source


def test_dependency_injection_pattern():
    """Verify ReconciliationService uses dependency injection."""
    import inspect
    from app.services.reconciliation import ReconciliationService
    
    # Check constructor signature
    sig = inspect.signature(ReconciliationService.__init__)
    params = list(sig.parameters.keys())
    
    # Should have repository parameters
    assert "transaction_repo" in params
    assert "reconciliation_repo" in params
    assert "match_repo" in params
    assert "decision_repo" in params
    assert "exception_repo" in params
    assert "audit_repo" in params
    
    # Should not create its own database connections
    source = inspect.getsource(ReconciliationService)
    assert "create_engine" not in source
    assert "sessionmaker" not in source
