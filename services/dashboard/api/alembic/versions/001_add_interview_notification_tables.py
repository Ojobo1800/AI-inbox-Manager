"""Add students, interview_events, and notification_drafts tables

Revision ID: 001_interview_tables
Revises:
Create Date: 2026-01-28

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_interview_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- students table ---
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("personal_email", sa.String(255), nullable=True),
        sa.Column("assigned_gmail", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(50), nullable=True),
        sa.Column("drive_folder_id", sa.String(255), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_students_username", "students", ["username"])
    op.create_index("ix_students_is_active", "students", ["is_active"])

    # --- interview_events table ---
    op.create_table(
        "interview_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email_id", sa.Integer(), sa.ForeignKey("emails.id"), nullable=False),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id"),
            nullable=True,
        ),
        sa.Column("sub_type", sa.String(100), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("position_title", sa.String(255), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(100), nullable=True),
        sa.Column("interview_date", sa.String(20), nullable=True),
        sa.Column("interview_time", sa.String(10), nullable=True),
        sa.Column("interview_timezone", sa.String(20), nullable=True),
        sa.Column("interview_format", sa.String(50), nullable=True),
        sa.Column("meeting_link", sa.Text(), nullable=True),
        sa.Column("num_interviewers", sa.Integer(), nullable=True),
        sa.Column("is_job_machine", sa.Boolean(), server_default="0"),
        sa.Column("is_next_round", sa.Boolean(), server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("raw_extraction", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_interview_events_email_id", "interview_events", ["email_id"])
    op.create_index("ix_interview_events_student_id", "interview_events", ["student_id"])
    op.create_index("ix_interview_events_sub_type", "interview_events", ["sub_type"])
    op.create_index("ix_interview_events_confidence", "interview_events", ["confidence"])
    op.create_index(
        "idx_interview_sub_type_date",
        "interview_events",
        ["sub_type", "created_at"],
    )
    op.create_index(
        "idx_interview_company",
        "interview_events",
        ["company_name"],
    )

    # --- notification_drafts table ---
    op.create_table(
        "notification_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "interview_event_id",
            sa.Integer(),
            sa.ForeignKey("interview_events.id"),
            nullable=False,
        ),
        sa.Column("template_id", sa.String(100), nullable=True),
        sa.Column("email_subject", sa.String(500), nullable=True),
        sa.Column("email_body", sa.Text(), nullable=True),
        sa.Column("recipient_email", sa.String(255), nullable=True),
        sa.Column("email_status", sa.String(50), server_default="draft"),
        sa.Column("auto_send_eligible", sa.Boolean(), server_default="0"),
        sa.Column("whatsapp_message", sa.Text(), nullable=True),
        sa.Column("whatsapp_recipient_phone", sa.String(50), nullable=True),
        sa.Column("whatsapp_sender_phone", sa.String(50), nullable=True),
        sa.Column("whatsapp_status", sa.String(50), server_default="draft"),
        sa.Column("missing_fields", sa.JSON(), nullable=True),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("send_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_notification_drafts_interview_event_id",
        "notification_drafts",
        ["interview_event_id"],
    )
    op.create_index(
        "ix_notification_drafts_email_status",
        "notification_drafts",
        ["email_status"],
    )
    op.create_index(
        "idx_draft_status",
        "notification_drafts",
        ["email_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("notification_drafts")
    op.drop_table("interview_events")
    op.drop_table("students")
