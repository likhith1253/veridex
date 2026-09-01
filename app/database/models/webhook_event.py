"""
Webhook Event ORM Model for Project Sentinel.

Tracks incoming webhook events from payment gateways (e.g. Razorpay)
to ensure durable idempotency and provide an immutable intake audit trail.
"""

from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, JSON, String, Text
from app.database.models.base import Base
from app.database.utils import utcnow


class WebhookEvent(Base):
    """ORM Model representing an incoming gateway webhook event for durable idempotency."""

    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(255), unique=True, index=True, nullable=False)
    event_type = Column(String(100), index=True, nullable=False)
    gateway = Column(String(50), default="razorpay", nullable=False)
    payload_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(50), default="PROCESSED", nullable=False)  # PROCESSED, DUPLICATE_IGNORED, FAILED
    error_message = Column(Text, nullable=True)
    received_at = Column(DateTime, default=utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<WebhookEvent(id='{self.id}', event_id='{self.event_id}', event_type='{self.event_type}', status='{self.status}')>"
