"""Create SCRUM-182 conversations and correlated agent-run traces."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum182_conversations"
down_revision = "scrum180_documents"
branch_labels = None
depends_on = None

uuid_type = postgresql.UUID(as_uuid=True)
timestamp_type = sa.DateTime(timezone=True)
jsonb_type = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "conversation_threads",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("subject_type", sa.String(40)),
        sa.Column("subject_id", uuid_type),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("archived_at", timestamp_type),
        sa.PrimaryKeyConstraint("id", name="pk_conversation_threads"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_conversation_threads_user_id_users", ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('active', 'archived', 'deleted')", name="ck_conversation_threads_status"),
    )
    op.create_index("ix_conversation_threads_user_updated", "conversation_threads", ["user_id", sa.text("updated_at DESC")])

    op.create_table(
        "conversation_messages",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("thread_id", uuid_type, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_json", jsonb_type),
        sa.Column("status", sa.String(30), nullable=False, server_default="completed"),
        sa.Column("parent_message_id", uuid_type),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_conversation_messages"),
        sa.ForeignKeyConstraint(["thread_id"], ["conversation_threads.id"], name="fk_conversation_messages_thread_id_conversation_threads", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_message_id"], ["conversation_messages.id"], name="fk_conversation_messages_parent_message_id_conversation_messages"),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')", name="ck_conversation_messages_role"),
        sa.CheckConstraint("status IN ('pending', 'completed', 'failed', 'redacted')", name="ck_conversation_messages_status"),
    )
    op.create_index("ix_conversation_messages_thread_created", "conversation_messages", ["thread_id", "created_at"])

    op.create_table(
        "agent_runs",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", uuid_type, nullable=False),
        sa.Column("parent_run_id", uuid_type),
        sa.Column("user_id", uuid_type),
        sa.Column("message_id", uuid_type),
        sa.Column("agent_name", sa.String(80), nullable=False),
        sa.Column("capability", sa.String(100), nullable=False),
        sa.Column("subject_type", sa.String(50)),
        sa.Column("subject_id", uuid_type),
        sa.Column("request_payload", jsonb_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response_payload", jsonb_type),
        sa.Column("model_metadata", jsonb_type, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("prompt_version", sa.String(80)),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", timestamp_type),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
        sa.ForeignKeyConstraint(["parent_run_id"], ["agent_runs.id"], name="fk_agent_runs_parent_run_id_agent_runs"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_agent_runs_user_id_users"),
        sa.ForeignKeyConstraint(["message_id"], ["conversation_messages.id"], name="fk_agent_runs_message_id_conversation_messages"),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="ck_agent_runs_status"),
    )
    op.create_index("ix_agent_runs_request_id", "agent_runs", ["request_id"])
    op.create_index("ix_agent_runs_parent_run_id", "agent_runs", ["parent_run_id"])
    op.create_index("ix_agent_runs_agent_capability", "agent_runs", ["agent_name", "capability"])
    op.create_index("ix_agent_runs_subject", "agent_runs", ["subject_type", "subject_id"])
    op.create_index("ix_agent_runs_user_started", "agent_runs", ["user_id", sa.text("started_at DESC")])


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("conversation_messages")
    op.drop_table("conversation_threads")
