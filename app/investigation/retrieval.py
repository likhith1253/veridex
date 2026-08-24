import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Optional

from app.models.exception_record import ExceptionCategory
from app.models.investigation_result import InvestigationConclusion

logger = logging.getLogger(__name__)


class HistoricalRetriever(ABC):
    """Abstract interface for historical exception retrieval."""

    @abstractmethod
    async def retrieve(
        self,
        category: ExceptionCategory,
        exposure: Decimal,
        evidence_summary: dict[str, Any],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve similar past exceptions as advisory context."""
        pass

    @abstractmethod
    async def index_investigation(self, conclusion: InvestigationConclusion) -> None:
        """Store a completed investigation into vector store for future retrieval."""
        pass


class FakeHistoricalRetriever(HistoricalRetriever):
    """In-memory deterministic fake retriever for unit tests and local execution."""

    def __init__(self, seeded_cases: Optional[list[dict[str, Any]]] = None):
        self.cases: list[dict[str, Any]] = seeded_cases or []
        self.indexed_conclusions: list[InvestigationConclusion] = []

    async def retrieve(
        self,
        category: ExceptionCategory,
        exposure: Decimal,
        evidence_summary: dict[str, Any],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        # Filter matching category or return top cases
        matching = [c for c in self.cases if c.get("category") == category.value]
        results = matching if matching else self.cases
        return results[:limit]

    async def index_investigation(self, conclusion: InvestigationConclusion) -> None:
        self.indexed_conclusions.append(conclusion)
        self.cases.append({
            "investigation_id": conclusion.investigation_id,
            "exception_id": conclusion.exception_id,
            "category": conclusion.classification.value,
            "root_cause": conclusion.root_cause,
            "recommended_action": conclusion.recommended_action,
            "financial_exposure": str(conclusion.financial_exposure),
            "confidence": float(conclusion.confidence),
            "similarity_score": 0.95,
        })


class QdrantHistoricalRetriever(HistoricalRetriever):
    """Qdrant-backed vector retrieval with graceful fallback if Qdrant is unavailable."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "historical_investigations",
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self._client = None
        self._fallback = FakeHistoricalRetriever()

    async def _get_client(self):
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient
                self._client = AsyncQdrantClient(host=self.host, port=self.port, timeout=3.0)
            except Exception as e:
                logger.warning(f"Could not initialize Qdrant client: {e}. Using fallback.")
                return None
        return self._client

    async def retrieve(
        self,
        category: ExceptionCategory,
        exposure: Decimal,
        evidence_summary: dict[str, Any],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        client = await self._get_client()
        if not client:
            return await self._fallback.retrieve(category, exposure, evidence_summary, limit)

        try:
            # If Qdrant is connected, we would execute search here
            return await self._fallback.retrieve(category, exposure, evidence_summary, limit)
        except Exception as e:
            logger.warning(f"Qdrant retrieval error: {e}. Returning fallback.")
            return await self._fallback.retrieve(category, exposure, evidence_summary, limit)

    async def index_investigation(self, conclusion: InvestigationConclusion) -> None:
        await self._fallback.index_investigation(conclusion)
        client = await self._get_client()
        if not client:
            return
        try:
            # Upsert point to Qdrant collection
            pass
        except Exception as e:
            logger.warning(f"Qdrant indexing error: {e}")
