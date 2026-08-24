"""add investigations table

Revision ID: a1b2c3d4e5f6
Revises: 0ca41a2f1f8a
Create Date: 2026-08-24 11:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '0ca41a2f1f8a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'investigations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('exception_id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('method', sa.String(length=50), nullable=False),
        sa.Column('root_cause', sa.String(length=1000), nullable=False),
        sa.Column('classification', sa.String(length=100), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('financial_exposure', sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column('expected_cost', sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column('recommended_action', sa.String(length=100), nullable=False),
        sa.Column('requires_human_review', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('llm_invoked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('llm_error', sa.String(length=500), nullable=True),
        sa.Column('historical_cases_used', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('llm_raw_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'completed'")),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['exception_id'], ['exceptions.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_runs.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('investigation_id')
    )
    op.create_index('ix_investigations_classification', 'investigations', ['classification'], unique=False)
    op.create_index('ix_investigations_exception_id', 'investigations', ['exception_id'], unique=False)
    op.create_index('ix_investigations_investigation_id', 'investigations', ['investigation_id'], unique=False)
    op.create_index('ix_investigations_run_id', 'investigations', ['run_id'], unique=False)
    op.create_index('ix_investigations_status', 'investigations', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_investigations_status', table_name='investigations')
    op.drop_index('ix_investigations_run_id', table_name='investigations')
    op.drop_index('ix_investigations_investigation_id', table_name='investigations')
    op.drop_index('ix_investigations_exception_id', table_name='investigations')
    op.drop_index('ix_investigations_classification', table_name='investigations')
    op.drop_table('investigations')
