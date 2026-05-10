"""camps.detail_url + index for source

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "camps",
        sa.Column("detail_url", sa.Text, nullable=True),
    )
    # source already exists since 0001 with default 'camfit'. Add index for
    # source-aware filtering (camps list by source, joins with source filter).
    op.create_index("idx_camps_source", "camps", ["source"])


def downgrade() -> None:
    op.drop_index("idx_camps_source", table_name="camps")
    op.drop_column("camps", "detail_url")
