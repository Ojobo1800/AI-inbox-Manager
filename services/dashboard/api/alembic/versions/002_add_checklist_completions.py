"""Add checklist_completions table for interview process checklists

Revision ID: 002_checklist_completions
Revises: 001_interview_tables
Create Date: 2026-01-28

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_checklist_completions"
down_revision: Union[str, None] = "001_interview_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checklist_completions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "interview_event_id",
            sa.Integer(),
            sa.ForeignKey("interview_events.id"),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("is_completed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("completed_by", sa.String(100), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_checklist_completions_event_id",
        "checklist_completions",
        ["interview_event_id"],
    )
    op.create_index(
        "idx_checklist_event_step",
        "checklist_completions",
        ["interview_event_id", "step_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("checklist_completions")
