from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.database.models import Transaction as TransactionORM, TransactionSource, TransactionStatus
from app.models.transaction import Transaction as TransactionDomain


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
        timestamp=domain.timestamp,
        narration=domain.narration,
        fee=domain.fee,
        tax=domain.tax,
        status=TransactionStatus(domain.status.value),
        metadata=domain.metadata,
        created_at=created_at,
    )


def orm_to_domain(orm: TransactionORM) -> TransactionDomain:
    """Convert ORM Transaction to domain Transaction."""
    from app.models.transaction import TransactionSource as DomainSource, TransactionStatus as DomainStatus

    return TransactionDomain(
        txn_id=orm.domain_transaction_id,
        source=DomainSource(orm.source.value),
        reference_number=orm.reference_number,
        amount=Decimal(orm.amount),
        currency=orm.currency,
        timestamp=orm.timestamp,
        narration=orm.narration,
        fee=Decimal(orm.fee) if orm.fee is not None else None,
        tax=Decimal(orm.tax) if orm.tax is not None else None,
        status=DomainStatus(orm.status.value),
        order_id=orm.order_id,
        metadata=orm.metadata,
    )
