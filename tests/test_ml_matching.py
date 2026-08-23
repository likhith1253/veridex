import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.matching.features import FeatureExtractor
from app.matching.ml_scorer import MLScorer, TrainingDataBuilder, train_test_split_by_logical_id, TrainingExample
from app.models.transaction import Transaction, TransactionSource, TransactionStatus


class TestFeatureExtractor:
    """Test feature extraction for ML scoring."""

    def test_feature_generation_produces_deterministic_values(self):
        """Feature generation produces deterministic values."""
        extractor = FeatureExtractor()
        txn1 = Transaction(
            txn_id="T1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        txn2 = Transaction(
            txn_id="T2",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        
        features1 = extractor.extract_features(txn1, txn2)
        features2 = extractor.extract_features(txn1, txn2)
        
        assert features1 == features2

    def test_all_features_are_numeric(self):
        """All features are numeric (no NaN/invalid)."""
        extractor = FeatureExtractor()
        txn1 = Transaction(
            txn_id="T1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        txn2 = Transaction(
            txn_id="T2",
            source=TransactionSource.LEDGER,
            amount=Decimal("95.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 2),
            status=TransactionStatus.COMPLETED
        )
        
        features = extractor.extract_features(txn1, txn2)
        
        for key, value in features.items():
            assert isinstance(value, (int, float))
            assert not (isinstance(value, float) and (value != value))  # Check for NaN

    def test_reference_similarity_uses_difflib_correctly(self):
        """Reference similarity uses difflib correctly."""
        extractor = FeatureExtractor()
        txn1 = Transaction(
            txn_id="T1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            reference_number="ABC123",
            status=TransactionStatus.COMPLETED
        )
        txn2 = Transaction(
            txn_id="T2",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            reference_number="ABC123",
            status=TransactionStatus.COMPLETED
        )
        
        features = extractor.extract_features(txn1, txn2)
        assert features["ref_similarity"] == 1.0
        
        txn3 = Transaction(
            txn_id="T3",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            reference_number="XYZ789",
            status=TransactionStatus.COMPLETED
        )
        
        features = extractor.extract_features(txn1, txn3)
        assert features["ref_similarity"] < 1.0
        assert features["ref_similarity"] >= 0.0

    def test_narration_similarity_uses_difflib_correctly(self):
        """Narration similarity uses difflib correctly."""
        extractor = FeatureExtractor()
        txn1 = Transaction(
            txn_id="T1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            narration="Payment for order 123",
            status=TransactionStatus.COMPLETED
        )
        txn2 = Transaction(
            txn_id="T2",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            narration="Payment for order 123",
            status=TransactionStatus.COMPLETED
        )
        
        features = extractor.extract_features(txn1, txn2)
        assert features["narration_similarity"] == 1.0

    def test_fee_tax_consistency_calculation_correct(self):
        """Fee/tax consistency calculation correct."""
        extractor = FeatureExtractor()
        txn1 = Transaction(
            txn_id="T1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            fee=Decimal("2.00"),
            tax=Decimal("1.00"),
            status=TransactionStatus.COMPLETED
        )
        txn2 = Transaction(
            txn_id="T2",
            source=TransactionSource.BANK,
            amount=Decimal("97.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        
        features = extractor.extract_features(txn1, txn2)
        # Expected: 100 - 2 - 1 = 97, which matches bank amount
        assert features["fee_tax_consistent"] == 1.0
        assert features["fee_tax_amount_diff"] == 0.0

    def test_settlement_window_binary_feature_correct(self):
        """Settlement window binary feature correct."""
        extractor = FeatureExtractor()
        txn1 = Transaction(
            txn_id="T1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        txn2 = Transaction(
            txn_id="T2",
            source=TransactionSource.BANK,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 5),
            status=TransactionStatus.COMPLETED
        )
        
        features = extractor.extract_features(txn1, txn2)
        assert features["settlement_window_7d"] == 1.0
        
        txn3 = Transaction(
            txn_id="T3",
            source=TransactionSource.BANK,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 10),
            status=TransactionStatus.COMPLETED
        )
        
        features = extractor.extract_features(txn1, txn3)
        assert features["settlement_window_7d"] == 0.0


class TestTrainingDataBuilder:
    """Test training data builder."""

    def test_training_data_builder_uses_candidate_generator_rules(self):
        """Training data builder uses CandidateGenerator blocking rules."""
        builder = TrainingDataBuilder()
        
        gateway_txn = Transaction(
            txn_id="G1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        ledger_txn = Transaction(
            txn_id="L1",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        bank_txn = Transaction(
            txn_id="B1",
            source=TransactionSource.BANK,
            amount=Decimal("97.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        
        ground_truth = {
            "TXN00000001": {
                "logical_transaction_id": "TXN00000001",
                "gateway_record_id": "G1",
                "ledger_record_id": "L1",
                "bank_record_id": "B1",
                "true_match": True,
                "true_exception": None,
                "true_amount": "100.00",
                "true_refund": None,
                "true_settlement_date": "2024-01-01T00:00:00",
                "financial_exposure": "0.00"
            }
        }
        
        examples = builder.build_from_simulator(
            [gateway_txn], [ledger_txn], [bank_txn], ground_truth
        )
        
        # Should generate examples for each source pair
        assert len(examples) > 0

    def test_positive_negative_labels_from_ground_truth(self):
        """Positive/negative labels from ground truth."""
        builder = TrainingDataBuilder()
        
        gateway_txn = Transaction(
            txn_id="G1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        ledger_txn1 = Transaction(
            txn_id="L1",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        ledger_txn2 = Transaction(
            txn_id="L2",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        bank_txn = Transaction(
            txn_id="B1",
            source=TransactionSource.BANK,
            amount=Decimal("97.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        
        ground_truth = {
            "TXN00000001": {
                "logical_transaction_id": "TXN00000001",
                "gateway_record_id": "G1",
                "ledger_record_id": "L1",
                "bank_record_id": "B1",
                "true_match": True,
                "true_exception": None,
                "true_amount": "100.00",
                "true_refund": None,
                "true_settlement_date": "2024-01-01T00:00:00",
                "financial_exposure": "0.00"
            }
        }
        
        examples = builder.build_from_simulator(
            [gateway_txn], [ledger_txn1, ledger_txn2], [bank_txn], ground_truth
        )
        
        # Should have both positive (label=1) and negative (label=0) examples
        labels = [ex.label for ex in examples]
        assert 1 in labels
        assert 0 in labels


class TestTrainTestSplit:
    """Test train/test split by logical ID."""

    def test_train_test_split_avoids_logical_transaction_leakage(self):
        """Train/test split avoids logical transaction leakage."""
        examples = []
        for i in range(10):
            txn1 = Transaction(
                txn_id=f"T{i}",
                source=TransactionSource.GATEWAY,
                amount=Decimal("100.00"),
                currency="INR",
                timestamp=datetime(2024, 1, 1),
                status=TransactionStatus.COMPLETED
            )
            txn2 = Transaction(
                txn_id=f"L{i}",
                source=TransactionSource.LEDGER,
                amount=Decimal("100.00"),
                currency="INR",
                timestamp=datetime(2024, 1, 1),
                status=TransactionStatus.COMPLETED
            )
            examples.append(TrainingExample(
                txn1=txn1,
                txn2=txn2,
                label=1,
                logical_transaction_id=f"LOGICAL{i % 3}"  # 3 logical IDs
            ))
        
        train, test = train_test_split_by_logical_id(examples, test_ratio=0.3, random_state=42)
        
        # Get logical IDs in each split
        train_ids = {ex.logical_transaction_id for ex in train}
        test_ids = {ex.logical_transaction_id for ex in test}
        
        # No overlap
        assert len(train_ids.intersection(test_ids)) == 0


class TestMLScorer:
    """Test ML scorer functionality."""

    def test_model_training_completes_without_error(self):
        """Model training completes without error."""
        scorer = MLScorer(model_type="logistic")
        
        features = [
            {"abs_amount_diff": 0.0, "rel_amount_diff": 0.0, "date_diff_days": 0.0,
             "settlement_window_7d": 1.0, "ref_similarity": 1.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0},
            {"abs_amount_diff": 10.0, "rel_amount_diff": 0.1, "date_diff_days": 5.0,
             "settlement_window_7d": 1.0, "ref_similarity": 0.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0}
        ]
        labels = [1, 0]
        
        scorer.train(features, labels)
        assert scorer.model is not None

    def test_probability_output_in_0_1_range(self):
        """Probability output in [0,1] range."""
        scorer = MLScorer(model_type="logistic")
        
        features = [
            {"abs_amount_diff": 0.0, "rel_amount_diff": 0.0, "date_diff_days": 0.0,
             "settlement_window_7d": 1.0, "ref_similarity": 1.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0},
            {"abs_amount_diff": 10.0, "rel_amount_diff": 0.1, "date_diff_days": 5.0,
             "settlement_window_7d": 1.0, "ref_similarity": 0.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0}
        ]
        labels = [1, 0]
        
        scorer.train(features, labels)
        probs = scorer.predict(features)
        
        for prob in probs:
            assert 0.0 <= prob <= 1.0

    def test_model_save_load_preserves_predictions(self):
        """Model save/load preserves predictions."""
        scorer = MLScorer(model_type="logistic")
        
        features = [
            {"abs_amount_diff": 0.0, "rel_amount_diff": 0.0, "date_diff_days": 0.0,
             "settlement_window_7d": 1.0, "ref_similarity": 1.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0},
            {"abs_amount_diff": 10.0, "rel_amount_diff": 0.1, "date_diff_days": 5.0,
             "settlement_window_7d": 1.0, "ref_similarity": 0.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0}
        ]
        labels = [1, 0]
        
        scorer.train(features, labels)
        probs_before = scorer.predict(features)
        
        # Save and load
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as f:
            temp_path = f.name
        
        try:
            scorer.save(temp_path)
            
            new_scorer = MLScorer(model_type="logistic")
            new_scorer.load(temp_path)
            probs_after = new_scorer.predict(features)
            
            # Predictions should be the same
            for p1, p2 in zip(probs_before, probs_after):
                assert abs(p1 - p2) < 1e-6
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_reproducibility_with_fixed_random_seed(self):
        """Reproducibility with fixed random seed."""
        scorer1 = MLScorer(model_type="logistic")
        scorer2 = MLScorer(model_type="logistic")
        
        features = [
            {"abs_amount_diff": 0.0, "rel_amount_diff": 0.0, "date_diff_days": 0.0,
             "settlement_window_7d": 1.0, "ref_similarity": 1.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0},
            {"abs_amount_diff": 10.0, "rel_amount_diff": 0.1, "date_diff_days": 5.0,
             "settlement_window_7d": 1.0, "ref_similarity": 0.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0}
        ]
        labels = [1, 0]
        
        scorer1.train(features, labels)
        scorer2.train(features, labels)
        
        probs1 = scorer1.predict(features)
        probs2 = scorer2.predict(features)
        
        for p1, p2 in zip(probs1, probs2):
            assert abs(p1 - p2) < 1e-6

    def test_logistic_regression_baseline_works(self):
        """Logistic Regression baseline works."""
        scorer = MLScorer(model_type="logistic")
        
        features = [
            {"abs_amount_diff": 0.0, "rel_amount_diff": 0.0, "date_diff_days": 0.0,
             "settlement_window_7d": 1.0, "ref_similarity": 1.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0},
            {"abs_amount_diff": 10.0, "rel_amount_diff": 0.1, "date_diff_days": 5.0,
             "settlement_window_7d": 1.0, "ref_similarity": 0.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0}
        ]
        labels = [1, 0]
        
        scorer.train(features, labels)
        probs = scorer.predict(features)
        
        assert len(probs) == 2
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_xgboost_final_model_works(self):
        """XGBoost final model works."""
        scorer = MLScorer(model_type="xgboost")
        
        features = [
            {"abs_amount_diff": 0.0, "rel_amount_diff": 0.0, "date_diff_days": 0.0,
             "settlement_window_7d": 1.0, "ref_similarity": 1.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0},
            {"abs_amount_diff": 10.0, "rel_amount_diff": 0.1, "date_diff_days": 5.0,
             "settlement_window_7d": 1.0, "ref_similarity": 0.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0}
        ]
        labels = [1, 0]
        
        scorer.train(features, labels)
        probs = scorer.predict(features)
        
        assert len(probs) == 2
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_basic_predictive_performance_measured(self):
        """Basic predictive performance measured (no specific target claimed)."""
        scorer = MLScorer(model_type="logistic")
        
        # Create simple training data
        features = []
        labels = []
        for i in range(20):
            if i < 10:
                # Positive examples: similar features
                features.append({
                    "abs_amount_diff": 0.0, "rel_amount_diff": 0.0, "date_diff_days": 0.0,
                    "settlement_window_7d": 1.0, "ref_similarity": 1.0, "narration_similarity": 0.0,
                    "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
                    "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
                    "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0
                })
                labels.append(1)
            else:
                # Negative examples: different features
                features.append({
                    "abs_amount_diff": 50.0, "rel_amount_diff": 0.5, "date_diff_days": 10.0,
                    "settlement_window_7d": 0.0, "ref_similarity": 0.0, "narration_similarity": 0.0,
                    "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
                    "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
                    "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0
                })
                labels.append(0)
        
        scorer.train(features, labels)
        probs = scorer.predict(features)
        
        # Check that positive examples get higher probabilities on average
        pos_probs = [p for p, l in zip(probs, labels) if l == 1]
        neg_probs = [p for p, l in zip(probs, labels) if l == 0]
        
        assert sum(pos_probs) / len(pos_probs) > sum(neg_probs) / len(neg_probs)


class TestIntegration:
    """Test integration with existing components."""

    def test_ml_scorer_integrates_with_candidate_generator(self):
        """ML scorer integrates with CandidateGenerator."""
        from app.matching.candidate import CandidateGenerator
        
        gateway_txn = Transaction(
            txn_id="G1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        ledger_txn = Transaction(
            txn_id="L1",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            status=TransactionStatus.COMPLETED
        )
        
        transactions_by_source = {
            TransactionSource.GATEWAY: [gateway_txn],
            TransactionSource.LEDGER: [ledger_txn],
        }
        
        candidate_gen = CandidateGenerator(transactions_by_source)
        candidates = candidate_gen.get_candidates(gateway_txn)
        
        assert len(candidates) == 1
        assert candidates[0].txn_id == "L1"

    def test_ml_probability_does_not_automatically_create_match_result(self):
        """ML probability does NOT automatically create MatchResult."""
        scorer = MLScorer(model_type="logistic")
        
        features = [
            {"abs_amount_diff": 0.0, "rel_amount_diff": 0.0, "date_diff_days": 0.0,
             "settlement_window_7d": 1.0, "ref_similarity": 1.0, "narration_similarity": 0.0,
             "currency_equal": 1.0, "order_id_equal": 0.0, "reference_equal": 0.0,
             "fee_tax_consistent": 0.0, "fee_tax_amount_diff": 0.0,
             "source_pair_gw_ledger": 1.0, "source_pair_gw_bank": 0.0, "source_pair_ledger_bank": 0.0}
        ]
        labels = [1]
        
        scorer.train(features, labels)
        prob = scorer.predict(features)[0]
        
        # MLScorer only returns probability, not MatchResult
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0

    def test_deterministic_matching_still_works_independently(self):
        """Deterministic matching still works independently."""
        from app.matching.deterministic import DeterministicMatcher
        
        gateway_txn = Transaction(
            txn_id="G1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            reference_number="REF123",
            status=TransactionStatus.COMPLETED
        )
        ledger_txn = Transaction(
            txn_id="L1",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2024, 1, 1),
            reference_number="REF123",
            status=TransactionStatus.COMPLETED
        )
        
        matcher = DeterministicMatcher()
        result = matcher.match_by_exact_reference(gateway_txn, ledger_txn)
        
        # Deterministic matching should work without ML
        assert result is not None

    def test_no_embeddings_llm_unnecessary_dependencies(self):
        """No embeddings/LLM/unnecessary dependencies."""
        # Check that the code only uses standard library and specified ML libs
        import app.matching.features as features_module
        import app.matching.ml_scorer as scorer_module
        
        # Features module should only use standard library
        features_source = open(features_module.__file__).read()
        assert "openai" not in features_source.lower()
        assert "anthropic" not in features_source.lower()
        assert "sentence_transformers" not in features_source.lower()
        
        # ML scorer should only use sklearn and xgboost
        scorer_source = open(scorer_module.__file__).read()
        assert "openai" not in scorer_source.lower()
        assert "anthropic" not in scorer_source.lower()
