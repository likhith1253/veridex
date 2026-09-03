from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from app.database.models import Transaction as TransactionORM, TransactionSource, TransactionStatus
from app.models.transaction import Transaction as TransactionDomain
from app.models.transaction import TransactionStatus as DomainStatus


# Translate domain payment status → ORM reconciliation processing status.
# The ORM enum tracks reconciliation pipeline state, not payment lifecycle.
_DOMAIN_TO_ORM_STATUS: dict[DomainStatus, TransactionStatus] = {
    DomainStatus.PENDING: TransactionStatus.PENDING,
    DomainStatus.COMPLETED: TransactionStatus.PROCESSED,
    DomainStatus.FAILED: TransactionStatus.EXCEPTION,
    DomainStatus.REFUNDED: TransactionStatus.PROCESSED,
    DomainStatus.PARTIALLY_REFUNDED: TransactionStatus.PROCESSED,
}

_ORM_TO_DOMAIN_STATUS: dict[Any, DomainStatus] = {
    TransactionStatus.PENDING: DomainStatus.PENDING,
    TransactionStatus.PROCESSED: DomainStatus.COMPLETED,
    TransactionStatus.EXCEPTION: DomainStatus.FAILED,
    "pending": DomainStatus.PENDING,
    "processed": DomainStatus.COMPLETED,
    "completed": DomainStatus.COMPLETED,
    "exception": DomainStatus.FAILED,
    "failed": DomainStatus.FAILED,
    "refunded": DomainStatus.REFUNDED,
    "partially_refunded": DomainStatus.PARTIALLY_REFUNDED,
}


def _domain_status_to_orm(domain_status: DomainStatus) -> TransactionStatus:
    orm_status = _DOMAIN_TO_ORM_STATUS.get(domain_status)
    if orm_status is None:
        raise ValueError(f"Unmapped domain TransactionStatus: {domain_status!r}")
    return orm_status


def _orm_status_to_domain(orm_status: Any) -> DomainStatus:
    if orm_status in _ORM_TO_DOMAIN_STATUS:
        return _ORM_TO_DOMAIN_STATUS[orm_status]
    str_status = (orm_status.value if hasattr(orm_status, "value") else str(orm_status)).lower()
    domain_status = _ORM_TO_DOMAIN_STATUS.get(str_status)
    if domain_status is not None:
        return domain_status
    return DomainStatus.COMPLETED



def domain_to_orm(domain: TransactionDomain, id: str, created_at: datetime) -> TransactionORM:
    """Convert domain Transaction to ORM Transaction."""
    return TransactionORM(
        id=id,
        domain_transaction_id=domain.txn_id,
        source=TransactionSource(domain.source.value),
        reference_number=domain.reference_number,
        order_id=domain.order_id,
        amount=domain.amount,
        currency=domain.currency,
        timestamp=domain.timestamp.replace(tzinfo=None) if domain.timestamp and domain.timestamp.tzinfo else domain.timestamp,
        narration=domain.narration,
        fee=domain.fee,
        tax=domain.tax,
        status=_domain_status_to_orm(domain.status),
        meta_data=domain.metadata,
        created_at=created_at.replace(tzinfo=None) if created_at and created_at.tzinfo else created_at,
    )


def orm_to_domain(orm: TransactionORM) -> TransactionDomain:
    """Convert ORM Transaction to domain Transaction."""
    from app.models.transaction import TransactionSource as DomainSource

    return TransactionDomain(
        txn_id=orm.domain_transaction_id,
        source=DomainSource(orm.source.value if hasattr(orm.source, "value") else str(orm.source)),
        reference_number=orm.reference_number,
        amount=Decimal(orm.amount),
        currency=orm.currency,
        timestamp=orm.timestamp,
        narration=orm.narration,
        fee=Decimal(orm.fee) if orm.fee is not None else None,
        tax=Decimal(orm.tax) if orm.tax is not None else None,
        status=_orm_status_to_domain(orm.status),
        order_id=orm.order_id,
        metadata=orm.meta_data,
    )
