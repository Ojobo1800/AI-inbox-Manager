import json
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings


def build_sqlserver_connection_url() -> str:
    driver = settings.sqlserver_driver.replace(" ", "+")
    return (
        f"mssql+pyodbc://{settings.sqlserver_user}:{settings.sqlserver_password}"
        f"@{settings.sqlserver_host}:{settings.sqlserver_port}/{settings.sqlserver_db}"
        f"?driver={driver}&TrustServerCertificate=yes"
    )


def get_engine() -> Engine:
    return create_engine(build_sqlserver_connection_url(), pool_pre_ping=True)


def ensure_gmail_checkpoint_table(engine: Engine | None = None) -> None:
    db_engine = engine or get_engine()
    ddl = text(
        """
        IF OBJECT_ID('dbo.gmail_sync_checkpoint', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.gmail_sync_checkpoint (
                id INT IDENTITY(1,1) PRIMARY KEY,
                email_address NVARCHAR(320) NOT NULL UNIQUE,
                history_id NVARCHAR(64) NOT NULL,
                pubsub_message_id NVARCHAR(128) NULL,
                pubsub_publish_time DATETIME2 NULL,
                updated_at_utc DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
        END
        """
    )

    with db_engine.begin() as conn:
        conn.execute(ddl)


def ensure_gmail_unread_intake_table(engine: Engine | None = None) -> None:
    db_engine = engine or get_engine()
    ddl = text(
        """
        IF OBJECT_ID('dbo.gmail_unread_intake', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.gmail_unread_intake (
                id INT IDENTITY(1,1) PRIMARY KEY,
                message_id NVARCHAR(128) NOT NULL UNIQUE,
                email_address NVARCHAR(320) NOT NULL,
                thread_id NVARCHAR(128) NULL,
                history_id NVARCHAR(64) NULL,
                subject NVARCHAR(1024) NULL,
                sender NVARCHAR(1024) NULL,
                sent_at NVARCHAR(256) NULL,
                snippet NVARCHAR(MAX) NULL,
                body_excerpt NVARCHAR(MAX) NULL,
                is_unread BIT NOT NULL,
                is_interview_related BIT NOT NULL,
                raw_json NVARCHAR(MAX) NULL,
                updated_at_utc DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
        END
        """
    )

    with db_engine.begin() as conn:
        conn.execute(ddl)


def ensure_interview_tracker_table(engine: Engine | None = None) -> None:
    db_engine = engine or get_engine()
    ddl = text(
        """
        IF OBJECT_ID('dbo.interview_tracker', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.interview_tracker (
                id INT IDENTITY(1,1) PRIMARY KEY,
                record_key NVARCHAR(128) NOT NULL UNIQUE,
                email_address NVARCHAR(320) NOT NULL,
                company_name NVARCHAR(256) NULL,
                position_title NVARCHAR(512) NULL,
                interview_type NVARCHAR(128) NULL,
                interview_datetime NVARCHAR(128) NULL,
                status NVARCHAR(64) NOT NULL,
                source NVARCHAR(64) NOT NULL,
                source_message_id NVARCHAR(128) NULL,
                subject NVARCHAR(1024) NULL,
                sender NVARCHAR(1024) NULL,
                snippet NVARCHAR(MAX) NULL,
                received_at NVARCHAR(128) NULL,
                updated_at_utc DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
        END
        """
    )

    with db_engine.begin() as conn:
        conn.execute(ddl)


def upsert_gmail_checkpoint(
    email_address: str,
    history_id: str,
    pubsub_message_id: str | None,
    pubsub_publish_time: str | None,
    engine: Engine | None = None,
) -> None:
    db_engine = engine or get_engine()
    ensure_gmail_checkpoint_table(db_engine)

    publish_dt: datetime | None = None
    if pubsub_publish_time:
        publish_dt = datetime.fromisoformat(pubsub_publish_time.replace("Z", "+00:00"))

    merge_sql = text(
        """
        MERGE dbo.gmail_sync_checkpoint AS target
        USING (
            SELECT
                :email_address AS email_address,
                :history_id AS history_id,
                :pubsub_message_id AS pubsub_message_id,
                :pubsub_publish_time AS pubsub_publish_time
        ) AS source
        ON target.email_address = source.email_address
        WHEN MATCHED THEN
            UPDATE SET
                history_id = source.history_id,
                pubsub_message_id = source.pubsub_message_id,
                pubsub_publish_time = source.pubsub_publish_time,
                updated_at_utc = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (
                email_address,
                history_id,
                pubsub_message_id,
                pubsub_publish_time,
                updated_at_utc
            )
            VALUES (
                source.email_address,
                source.history_id,
                source.pubsub_message_id,
                source.pubsub_publish_time,
                SYSUTCDATETIME()
            );
        """
    )

    with db_engine.begin() as conn:
        conn.execute(
            merge_sql,
            {
                "email_address": email_address,
                "history_id": history_id,
                "pubsub_message_id": pubsub_message_id,
                "pubsub_publish_time": publish_dt,
            },
        )


def upsert_unread_intake_email(email_address: str, message: dict[str, Any], engine: Engine | None = None) -> None:
    db_engine = engine or get_engine()
    ensure_gmail_unread_intake_table(db_engine)

    merge_sql = text(
        """
        MERGE dbo.gmail_unread_intake AS target
        USING (
            SELECT
                :message_id AS message_id,
                :email_address AS email_address,
                :thread_id AS thread_id,
                :history_id AS history_id,
                :subject AS subject,
                :sender AS sender,
                :sent_at AS sent_at,
                :snippet AS snippet,
                :body_excerpt AS body_excerpt,
                :is_unread AS is_unread,
                :is_interview_related AS is_interview_related,
                :raw_json AS raw_json
        ) AS source
        ON target.message_id = source.message_id
        WHEN MATCHED THEN
            UPDATE SET
                email_address = source.email_address,
                thread_id = source.thread_id,
                history_id = source.history_id,
                subject = source.subject,
                sender = source.sender,
                sent_at = source.sent_at,
                snippet = source.snippet,
                body_excerpt = source.body_excerpt,
                is_unread = source.is_unread,
                is_interview_related = source.is_interview_related,
                raw_json = source.raw_json,
                updated_at_utc = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (
                message_id,
                email_address,
                thread_id,
                history_id,
                subject,
                sender,
                sent_at,
                snippet,
                body_excerpt,
                is_unread,
                is_interview_related,
                raw_json,
                updated_at_utc
            )
            VALUES (
                source.message_id,
                source.email_address,
                source.thread_id,
                source.history_id,
                source.subject,
                source.sender,
                source.sent_at,
                source.snippet,
                source.body_excerpt,
                source.is_unread,
                source.is_interview_related,
                source.raw_json,
                SYSUTCDATETIME()
            );
        """
    )

    with db_engine.begin() as conn:
        conn.execute(
            merge_sql,
            {
                "message_id": message.get("message_id"),
                "email_address": email_address,
                "thread_id": message.get("thread_id"),
                "history_id": message.get("history_id"),
                "subject": message.get("subject"),
                "sender": message.get("sender"),
                "sent_at": message.get("sent_at"),
                "snippet": message.get("snippet"),
                "body_excerpt": message.get("body_excerpt"),
                "is_unread": bool(message.get("is_unread", False)),
                "is_interview_related": bool(message.get("is_interview_related", False)),
                "raw_json": json.dumps(message.get("raw", {})),
            },
        )


def upsert_interview_tracker_record(record: dict[str, Any], engine: Engine | None = None) -> None:
    db_engine = engine or get_engine()
    ensure_interview_tracker_table(db_engine)

    merge_sql = text(
        """
        MERGE dbo.interview_tracker AS target
        USING (
            SELECT
                :record_key AS record_key,
                :email_address AS email_address,
                :company_name AS company_name,
                :position_title AS position_title,
                :interview_type AS interview_type,
                :interview_datetime AS interview_datetime,
                :status AS status,
                :source AS source,
                :source_message_id AS source_message_id,
                :subject AS subject,
                :sender AS sender,
                :snippet AS snippet,
                :received_at AS received_at
        ) AS source
        ON target.record_key = source.record_key
        WHEN MATCHED THEN
            UPDATE SET
                email_address = source.email_address,
                company_name = source.company_name,
                position_title = source.position_title,
                interview_type = source.interview_type,
                interview_datetime = source.interview_datetime,
                status = source.status,
                source = source.source,
                source_message_id = source.source_message_id,
                subject = source.subject,
                sender = source.sender,
                snippet = source.snippet,
                received_at = source.received_at,
                updated_at_utc = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (
                record_key,
                email_address,
                company_name,
                position_title,
                interview_type,
                interview_datetime,
                status,
                source,
                source_message_id,
                subject,
                sender,
                snippet,
                received_at,
                updated_at_utc
            )
            VALUES (
                source.record_key,
                source.email_address,
                source.company_name,
                source.position_title,
                source.interview_type,
                source.interview_datetime,
                source.status,
                source.source,
                source.source_message_id,
                source.subject,
                source.sender,
                source.snippet,
                source.received_at,
                SYSUTCDATETIME()
            );
        """
    )

    with db_engine.begin() as conn:
        conn.execute(merge_sql, record)


def get_gmail_checkpoint(email_address: str, engine: Engine | None = None) -> dict[str, Any] | None:
    db_engine = engine or get_engine()

    query = text(
        """
        SELECT TOP 1
            email_address,
            history_id,
            pubsub_message_id,
            pubsub_publish_time,
            updated_at_utc
        FROM dbo.gmail_sync_checkpoint
        WHERE email_address = :email_address
        """
    )

    with db_engine.begin() as conn:
        row = conn.execute(query, {"email_address": email_address}).mappings().first()

    return dict(row) if row else None
