import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConversationThread(Base):
    __tablename__ = "conversation_threads"
    __table_args__ = (
        Index("ix_conversation_threads_user_updated", "user_id", text("updated_at DESC")),
        CheckConstraint("status IN ('active', 'archived', 'deleted')", name="conversation_threads_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    subject_type: Mapped[str | None] = mapped_column(String(40))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["ConversationMessage"]] = relationship(back_populates="thread", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("ix_conversation_messages_thread_created", "thread_id", "created_at"),
        CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')", name="conversation_messages_role"),
        CheckConstraint("status IN ('pending', 'completed', 'failed', 'redacted')", name="conversation_messages_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_threads.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict | list | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="completed")
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversation_messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    thread: Mapped[ConversationThread] = relationship(back_populates="messages")
    parent_message: Mapped["ConversationMessage | None"] = relationship(remote_side="ConversationMessage.id")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_request_id", "request_id"),
        Index("ix_agent_runs_parent_run_id", "parent_run_id"),
        Index("ix_agent_runs_agent_capability", "agent_name", "capability"),
        Index("ix_agent_runs_subject", "subject_type", "subject_id"),
        Index("ix_agent_runs_user_started", "user_id", text("started_at DESC")),
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="agent_runs_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversation_messages.id"))
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    capability: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_type: Mapped[str | None] = mapped_column(String(50))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    response_payload: Mapped[dict | None] = mapped_column(JSONB)
    model_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="queued")
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    parent_run: Mapped["AgentRun | None"] = relationship(remote_side="AgentRun.id", back_populates="child_runs")
    child_runs: Mapped[list["AgentRun"]] = relationship(back_populates="parent_run")
