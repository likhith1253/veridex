import logging
from typing import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Security
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.database.repositories import (
    AuditRepository,
    DecisionRepository,
    ExceptionRepository,
    InvestigationRepository,
    MatchRepository,
    ReconciliationRepository,
    TransactionRepository,
)
from app.database.session import async_session_maker
from app.investigation.service import InvestigationService
from app.services.reconciliation import ReconciliationService


from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing a transactional database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except (HTTPException, StarletteHTTPException, RequestValidationError):
            await session.rollback()
            raise
        except Exception as e:
            logger.error("DB session error: %s", e, exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()


def get_investigation_repository(
    session: AsyncSession = Depends(get_db_session),
) -> InvestigationRepository:
    """Dependency for InvestigationRepository."""
    return InvestigationRepository(session)


def get_audit_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AuditRepository:
    """Dependency for AuditRepository."""
    return AuditRepository(session)


def get_reconciliation_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ReconciliationRepository:
    """Dependency for ReconciliationRepository."""
    return ReconciliationRepository(session)


def get_transaction_repository(
    session: AsyncSession = Depends(get_db_session),
) -> TransactionRepository:
    """Dependency for TransactionRepository."""
    return TransactionRepository(session)


def get_match_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MatchRepository:
    """Dependency for MatchRepository."""
    return MatchRepository(session)


def get_decision_repository(
    session: AsyncSession = Depends(get_db_session),
) -> DecisionRepository:
    """Dependency for DecisionRepository."""
    return DecisionRepository(session)


def get_exception_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ExceptionRepository:
    """Dependency for ExceptionRepository."""
    return ExceptionRepository(session)


from fastapi.security import APIKeyHeader
from typing import Optional
import os
from app.graph.investigation_graph import InvestigationGraphRunner
from app.investigation.llm_client import FakeLLMClient, GroqLLMClient, LLMClient

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Verify API key authentication when VERIDEX_API_KEY / SENTINEL_API_KEY / API_KEY is configured."""
    configured_key = (
        os.environ.get("VERIDEX_API_KEY")
        or os.environ.get("SENTINEL_API_KEY")
        or os.environ.get("API_KEY")
        or ""
    ).strip()
    if not configured_key:
        return None

    provided_key = None
    if api_key:
        provided_key = api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        provided_key = authorization[7:].strip()

    if not provided_key or provided_key != configured_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return provided_key


def get_llm_client() -> LLMClient:
    """Dependency for LLM client: GroqLLMClient if GROQ_API_KEY is available, else FakeLLMClient."""
    api_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if api_key:
        return GroqLLMClient(api_key=api_key)
    return FakeLLMClient()


def get_investigation_graph_runner(
    llm_client: LLMClient = Depends(get_llm_client),
) -> InvestigationGraphRunner:
    """Dependency for InvestigationGraphRunner."""
    return InvestigationGraphRunner(llm_client=llm_client)


def get_investigation_service(
    session: AsyncSession = Depends(get_db_session),
    investigation_repo: InvestigationRepository = Depends(get_investigation_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    graph_runner: InvestigationGraphRunner = Depends(get_investigation_graph_runner),
) -> InvestigationService:
    """Dependency for InvestigationService."""
    return InvestigationService(
        session=session,
        investigation_repo=investigation_repo,
        audit_repo=audit_repo,
        graph_runner=graph_runner,
    )


def get_reconciliation_service(
    session: AsyncSession = Depends(get_db_session),
    transaction_repo: TransactionRepository = Depends(get_transaction_repository),
    reconciliation_repo: ReconciliationRepository = Depends(get_reconciliation_repository),
    match_repo: MatchRepository = Depends(get_match_repository),
    decision_repo: DecisionRepository = Depends(get_decision_repository),
    exception_repo: ExceptionRepository = Depends(get_exception_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> ReconciliationService:
    """Dependency for ReconciliationService with investigation capabilities wired."""
    return ReconciliationService(
        session=session,
        transaction_repo=transaction_repo,
        reconciliation_repo=reconciliation_repo,
        match_repo=match_repo,
        decision_repo=decision_repo,
        exception_repo=exception_repo,
        audit_repo=audit_repo,
        investigation_service=investigation_service,
    )
