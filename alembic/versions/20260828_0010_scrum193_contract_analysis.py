"""Add immutable extracted text and contract analyses."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum193_contract_analysis"
down_revision = "scrum192_startup_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.create_table(
        "contract_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy", sa.String(length=60), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="running", nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_contract_analyses"),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="contract_analyses_status"),
    )
    op.create_index("ix_contract_analyses_project_created", "contract_analyses", ["project_id", "created_at"])
    op.create_index("ix_contract_analyses_document_version", "contract_analyses", ["document_version_id"])
    op.create_table(
        "contract_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_index", sa.Integer(), nullable=False),
        sa.Column("finding_type", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("uncertainty", sa.Text(), nullable=True),
        sa.Column("evidence_document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("evidence_start_char", sa.Integer(), nullable=False),
        sa.Column("evidence_end_char", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["contract_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_document_version_id"], ["document_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_contract_findings"),
        sa.CheckConstraint("finding_type IN ('FINDING', 'RISK', 'RECOMMENDATION', 'UNCERTAINTY')", name="contract_findings_type"),
        sa.CheckConstraint("evidence_start_char >= 0 AND evidence_end_char > evidence_start_char", name="contract_findings_evidence_span"),
    )
    op.create_index("ix_contract_findings_analysis_index", "contract_findings", ["analysis_id", "finding_index"])


def downgrade() -> None:
    op.drop_index("ix_contract_findings_analysis_index", table_name="contract_findings")
    op.drop_table("contract_findings")
    op.drop_index("ix_contract_analyses_document_version", table_name="contract_analyses")
    op.drop_index("ix_contract_analyses_project_created", table_name="contract_analyses")
    op.drop_table("contract_analyses")
    op.drop_column("document_versions", "extracted_text")
