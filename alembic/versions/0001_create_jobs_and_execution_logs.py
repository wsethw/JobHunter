from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_create_jobs_and_execution_logs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column(
            "stack",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("link", sa.String(length=500), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seniority", sa.String(length=50), nullable=True),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("score_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("salary_min", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("salary_currency", sa.String(length=10), nullable=True),
        sa.Column("contract_type", sa.String(length=50), nullable=True),
        sa.Column("remote_type", sa.String(length=50), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
        sa.Column("seen_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)", name="ck_jobs_score_range"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link"),
    )
    op.create_index("idx_jobs_created_at", "jobs", ["created_at"])
    op.create_index("idx_jobs_last_seen_at", "jobs", ["last_seen_at"])
    op.create_index("idx_jobs_source", "jobs", ["source"])
    op.create_index("idx_jobs_score", "jobs", ["score"])
    op.create_index("idx_jobs_fingerprint", "jobs", ["fingerprint"])
    op.create_index("idx_jobs_content_hash", "jobs", ["content_hash"])
    op.create_index("idx_jobs_source_external_id", "jobs", ["source", "external_id"])
    op.create_index("idx_jobs_stack_gin", "jobs", ["stack"], postgresql_using="gin")

    op.create_table(
        "execution_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sources_scraped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_new", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_execution_logs_started_at", "execution_logs", ["started_at"])
    op.create_index("idx_execution_logs_status", "execution_logs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_execution_logs_status", table_name="execution_logs")
    op.drop_index("idx_execution_logs_started_at", table_name="execution_logs")
    op.drop_table("execution_logs")
    op.drop_index("idx_jobs_stack_gin", table_name="jobs")
    op.drop_index("idx_jobs_source_external_id", table_name="jobs")
    op.drop_index("idx_jobs_content_hash", table_name="jobs")
    op.drop_index("idx_jobs_fingerprint", table_name="jobs")
    op.drop_index("idx_jobs_score", table_name="jobs")
    op.drop_index("idx_jobs_source", table_name="jobs")
    op.drop_index("idx_jobs_last_seen_at", table_name="jobs")
    op.drop_index("idx_jobs_created_at", table_name="jobs")
    op.drop_table("jobs")
