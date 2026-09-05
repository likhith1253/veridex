"""add webhook_events table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-05 14:00:00.000000

The WebhookEvent ORM model (app/database/models/webhook_event.py) has existed
since Razorpay webhook support was added, but no migration was ever authored
for it — the table only ever existed in environments where
app.database.session.init_db() (Base.metadata.create_all) had been run
manually, which masked the gap in local development. Any environment
provisioned purely via `alembic upgrade head` (a fresh Neon database, for
instance) was missing this table entirely, causing every real webhook to
crash with UndefinedTableError.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('gateway', sa.String(length=50), nullable=False, server_default=sa.text("'razorpay'")),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'PROCESSED'")),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id'),
    )
    op.create_index('ix_webhook_events_event_id', 'webhook_events', ['event_id'], unique=False)
    op.create_index('ix_webhook_events_event_type', 'webhook_events', ['event_type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_webhook_events_event_type', table_name='webhook_events')
    op.drop_index('ix_webhook_events_event_id', table_name='webhook_events')
    op.drop_table('webhook_events')
