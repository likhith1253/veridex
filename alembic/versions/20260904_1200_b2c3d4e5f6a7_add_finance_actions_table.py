"""add finance_actions table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'finance_actions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('state', sa.String(length=50), nullable=False, server_default=sa.text("'DETECTED'")),
        sa.Column('amount', sa.Numeric(precision=18, scale=4), nullable=False, server_default=sa.text('0.00')),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default=sa.text("'INR'")),
        sa.Column('recommended_by', sa.String(length=100), nullable=False),
        sa.Column('recommendation_reason', sa.String(length=1000), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('requested_by', sa.String(length=100), nullable=True),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('rejected_by', sa.String(length=100), nullable=True),
        sa.Column('decision_reason', sa.String(length=1000), nullable=True),
        sa.Column('execution_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_runs.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_finance_actions_entity_id', 'finance_actions', ['entity_id'], unique=False)
    op.create_index('ix_finance_actions_state', 'finance_actions', ['state'], unique=False)
    op.create_index('ix_finance_actions_run_id', 'finance_actions', ['run_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_finance_actions_run_id', table_name='finance_actions')
    op.drop_index('ix_finance_actions_state', table_name='finance_actions')
    op.drop_index('ix_finance_actions_entity_id', table_name='finance_actions')
    op.drop_table('finance_actions')
