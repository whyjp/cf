"""marks system

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "camp_marks",
        sa.Column("camp_id", sa.Text, sa.ForeignKey("camps.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("axis", sa.Text, primary_key=True),     # 'management' | 'view' | 'kids' | ...
        sa.Column("level", sa.Text, nullable=False),       # 'bib'|'recommended'|'notable'|'exceptional'
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column("evidence", sa.Text),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "level IN ('bib','recommended','notable','exceptional')",
            name="mark_level_check",
        ),
    )
    op.create_index("idx_camp_marks_axis_level", "camp_marks", ["axis", "level"])
    op.create_index("idx_camp_marks_axis_score", "camp_marks", ["axis", sa.text("score DESC")])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS camp_marks CASCADE")
