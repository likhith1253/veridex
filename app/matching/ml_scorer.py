from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.matching.candidate import CandidateGenerator
from app.matching.features import FeatureExtractor
from app.models.transaction import Transaction, TransactionSource


@dataclass
class TrainingExample:
    """A single training example for ML scoring."""
    txn1: Transaction
    txn2: Transaction
    label: int  # 1 for true match, 0 for false
    logical_transaction_id: str


class MLScorer:
    """ML-based candidate scorer using XGBoost or Logistic Regression."""

    def __init__(self, model_type: str = "xgboost", artifact_path: Optional[str] = None):
        """
        Initialize ML scorer.
        
        Args:
            model_type: "xgboost" or "logistic"
            artifact_path: Optional path to serialized model artifact
        """
        self.model_type = model_type
        self.model = None
        self.feature_extractor = FeatureExtractor()
        self._initialize_model()

        if artifact_path:
            self.load(str(artifact_path))
        elif self.model_type == "xgboost":
            from pathlib import Path
            default_path = Path("ml/artifacts/model.xgb")
            if default_path.exists():
                try:
                    self.load(str(default_path))
                except Exception:
                    pass

    def _initialize_model(self):
        """Initialize the model based on model_type."""
        if self.model_type == "xgboost":
            self.model = XGBClassifier(
                max_depth=3,
                n_estimators=50,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric="logloss"
            )
        elif self.model_type == "logistic":
            self.model = LogisticRegression(random_state=42)
        else:
            raise ValueError(f"Unsupported model_type: {self.model_type}")

    def train(self, features: list[dict[str, float]], labels: list[int]) -> None:
        """
        Train the model on features and labels.
        
        Args:
            features: List of feature dictionaries
            labels: List of binary labels (0 or 1)
        """
        # Convert features to numpy array
        feature_matrix = self._features_to_matrix(features)
        
        # Train model
        self.model.fit(feature_matrix, labels)

    def predict(self, features: list[dict[str, float]]) -> list[float]:
        """
        Predict match probability for candidate pairs.
        
        Args:
            features: List of feature dictionaries
            
        Returns:
            List of probabilities in [0, 1] range
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        
        feature_matrix = self._features_to_matrix(features)
        probabilities = self.model.predict_proba(feature_matrix)
        
        # Return probability of positive class (index 1)
        return [float(p[1]) for p in probabilities]

    def _features_to_matrix(self, features: list[dict[str, float]]) -> np.ndarray:
        """Convert list of feature dicts to numpy matrix."""
        if not features:
            return np.array([])
        
        # Get feature names from first example
        feature_names = list(features[0].keys())
        
        # Build matrix
        matrix = []
        for feat_dict in features:
            row = [feat_dict.get(name, 0.0) for name in feature_names]
            matrix.append(row)
        
        return np.array(matrix)

    def save(self, filepath: str) -> None:
        """Save model artifact to file."""
        if self.model is None:
            raise RuntimeError("No model to save.")
        
        if self.model_type == "xgboost":
            self.model.save_model(filepath)
        else:
            import joblib
            joblib.dump(self.model, filepath)

    def load(self, filepath: str) -> None:
        """Load model artifact from file."""
        if self.model_type == "xgboost":
            self.model = XGBClassifier(
                max_depth=3,
                n_estimators=50,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric="logloss"
            )
            self.model.load_model(filepath)
        else:
            import joblib
            self.model = joblib.load(filepath)


class TrainingDataBuilder:
    """Builds training data from simulator output using ground truth."""

    def __init__(self):
        self.feature_extractor = FeatureExtractor()

    def build_from_simulator(
        self,
        gateway_txns: list[Transaction],
        ledger_txns: list[Transaction],
        bank_txns: list[Transaction],
        ground_truth: dict,
    ) -> list[TrainingExample]:
        """
        Generate training examples from simulator data.
        
        Args:
            gateway_txns: List of gateway transactions
            ledger_txns: List of ledger transactions
            bank_txns: List of bank transactions
            ground_truth: Ground truth dictionary from simulator
            
        Returns:
            List of TrainingExample objects
        """
        # Group transactions by source
        transactions_by_source = {
            TransactionSource.GATEWAY: gateway_txns,
            TransactionSource.LEDGER: ledger_txns,
            TransactionSource.BANK: bank_txns,
        }
        
        # Create candidate generator
        candidate_gen = CandidateGenerator(transactions_by_source)
        
        examples = []
        
        # Build a mapping of record IDs to transactions (including settlement_id)
        all_txns = gateway_txns + ledger_txns + bank_txns
        txn_by_id = {}
        for txn in all_txns:
            txn_by_id[txn.txn_id] = txn
            if txn.metadata and "settlement_id" in txn.metadata:
                txn_by_id[txn.metadata["settlement_id"]] = txn
        
        # Handle ground_truth as dict or GroundTruth container
        gt_items = ground_truth.records.items() if hasattr(ground_truth, "records") else ground_truth.items()
        
        # Iterate through ground truth records
        for logical_id, gt_record in gt_items:
            # Extract record IDs and true_match status
            if isinstance(gt_record, dict):
                gw_id = gt_record.get("gateway_record_id")
                ld_id = gt_record.get("ledger_record_id")
                bk_id = gt_record.get("bank_record_id")
                is_true_match = gt_record.get("true_match", True)
            else:
                gw_id = getattr(gt_record, "gateway_record_id", None)
                ld_id = getattr(gt_record, "ledger_record_id", None)
                bk_id = getattr(gt_record, "bank_record_id", None)
                is_true_match = getattr(gt_record, "true_match", True)

            gateway_txn = txn_by_id.get(gw_id)
            ledger_txn = txn_by_id.get(ld_id)
            bank_txn = txn_by_id.get(bk_id)
            
            if not all([gateway_txn, ledger_txn, bank_txn]):
                continue
            
            # Generate candidates for each source pair
            true_pairs = [
                (gateway_txn, ledger_txn),
                (gateway_txn, bank_txn),
                (ledger_txn, bank_txn),
            ]
            
            for txn1, txn2 in true_pairs:
                # Get candidates using CandidateGenerator blocking rules
                candidates = candidate_gen.get_candidates(txn1)
                
                # Positive example (if true match) or negative (if non-match scenario)
                examples.append(TrainingExample(
                    txn1=txn1,
                    txn2=txn2,
                    label=1 if is_true_match else 0,
                    logical_transaction_id=logical_id
                ))
                
                # Add negative examples (candidates that are not the true match)
                for candidate in candidates:
                    if candidate.txn_id != txn2.txn_id:
                        examples.append(TrainingExample(
                            txn1=txn1,
                            txn2=candidate,
                            label=0,
                            logical_transaction_id=logical_id
                        ))
        
        return examples

    def examples_to_features(
        self, examples: list[TrainingExample]
    ) -> tuple[list[dict[str, float]], list[int]]:
        """
        Convert training examples to features and labels.
        
        Args:
            examples: List of TrainingExample objects
            
        Returns:
            Tuple of (features list, labels list)
        """
        features = []
        labels = []
        
        for example in examples:
            feat = self.feature_extractor.extract_features(example.txn1, example.txn2)
            features.append(feat)
            labels.append(example.label)
        
        return features, labels


def train_test_split_by_logical_id(
    examples: list[TrainingExample], test_ratio: float = 0.2, random_state: int = 42
) -> tuple[list[TrainingExample], list[TrainingExample]]:
    """
    Split examples into train/test sets grouped by logical_transaction_id.
    
    This prevents leakage by ensuring all examples from the same logical
    transaction are in the same split.
    
    Args:
        examples: List of TrainingExample objects
        test_ratio: Fraction of data for test set
        random_state: Random seed for reproducibility
        
    Returns:
        Tuple of (train_examples, test_examples)
    """
    # Group examples by logical_transaction_id
    groups = {}
    for example in examples:
        logical_id = example.logical_transaction_id
        if logical_id not in groups:
            groups[logical_id] = []
        groups[logical_id].append(example)
    
    # Get list of logical IDs
    logical_ids = list(groups.keys())
    
    # Split logical IDs
    train_ids, test_ids = train_test_split(
        logical_ids, test_size=test_ratio, random_state=random_state
    )
    
    # Build train and test sets
    train_examples = []
    test_examples = []
    
    for logical_id in train_ids:
        train_examples.extend(groups[logical_id])
    
    for logical_id in test_ids:
        test_examples.extend(groups[logical_id])
    
    return train_examples, test_examples
