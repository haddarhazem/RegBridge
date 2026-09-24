"""Align contract analysis persistence with V2.1 clause records.

Revision ID: contract_agent_analyzer
Revises: project_fact_deleted_history
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "contract_agent_analyzer"
down_revision = "project_fact_deleted_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create V2.1's clause table before retiring the former evidence-only
    # finding table. Existing rows are retained as source-only clauses.
    op.create_table(
        "contract_clauses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("contract_analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause_order", sa.Integer(), nullable=False),
        sa.Column("clause_type", sa.String(length=120), nullable=True),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=30), server_default="unknown", nullable=False),
        sa.Column("finding", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contract_analysis_id"], ["contract_analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_contract_clauses"),
        sa.UniqueConstraint("contract_analysis_id", "clause_order", name="uq_contract_clauses_analysis_order"),
    )

    op.add_column("contract_analyses", sa.Column("analysis_version", sa.Integer(), nullable=True))
    op.add_column("contract_analyses", sa.Column("contract_type", sa.String(length=100), nullable=True))
    op.add_column("contract_analyses", sa.Column("overall_risk_level", sa.String(length=30), nullable=True))
    op.add_column("contract_analyses", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("contract_analyses", sa.Column("recommendations", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("contract_analyses", sa.Column("missing_context", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("contract_analyses", sa.Column("verification_status", sa.String(length=30), server_default="pending", nullable=False))

    op.execute("""
        WITH numbered AS (
            SELECT id, row_number() OVER (PARTITION BY document_version_id ORDER BY created_at, id) AS analysis_version
            FROM contract_analyses
        )
        UPDATE contract_analyses AS analysis
        SET analysis_version = numbered.analysis_version,
            verification_status = CASE analysis.status
                WHEN 'completed' THEN 'completed'
                WHEN 'failed' THEN 'failed'
                ELSE 'running'
            END,
            overall_risk_level = 'unknown'
        FROM numbered
        WHERE analysis.id = numbered.id
    """)
    op.alter_column("contract_analyses", "analysis_version", nullable=False)
    op.create_unique_constraint("uq_contract_analyses_version", "contract_analyses", ["document_version_id", "analysis_version"])
    op.create_check_constraint("contract_analyses_overall_risk_level", "contract_analyses", "overall_risk_level IN ('low', 'medium', 'high', 'critical', 'unknown')")
    op.create_index("ix_contract_analyses_project_id", "contract_analyses", ["project_id"])

    op.execute("""
        INSERT INTO contract_clauses (
            id, contract_analysis_id, clause_order, clause_type, heading,
            extracted_text, risk_level, finding, recommendation, source_refs,
            confidence, created_at
        )
        SELECT
            gen_random_uuid(), finding.analysis_id, finding.finding_index,
            finding.category, finding.category, finding.evidence_quote,
            COALESCE(NULLIF(lower(finding.risk_level), ''), 'unknown'),
            finding.statement, finding.recommendation,
            jsonb_build_object(
                'evidence', jsonb_build_array(jsonb_build_object(
                    'document_version_id', finding.evidence_document_version_id,
                    'quote', finding.evidence_quote,
                    'start_char', finding.evidence_start_char,
                    'end_char', finding.evidence_end_char,
                    'locator', 'Historical evidence span'
                )),
                'analysis', jsonb_build_object(
                    'title', finding.category,
                    'status', 'FOUND',
                    'plain_language_summary', 'Passage historique conservé avec sa preuve.',
                    'purpose', 'Le contexte complet de cette analyse historique doit être revu dans le document source.',
                    'issues', jsonb_build_array(finding.statement),
                    'limitations', jsonb_build_array('Analyse antérieure migrée comme extrait lié à une preuve.')
                )
            ),
            NULL, finding.created_at
        FROM contract_findings AS finding
    """)

    op.drop_index("ix_contract_findings_analysis_index", table_name="contract_findings")
    op.drop_table("contract_findings")
    op.drop_index("ix_contract_analyses_project_created", table_name="contract_analyses")
    op.execute("ALTER TABLE contract_analyses DROP CONSTRAINT IF EXISTS contract_analyses_status")
    # The previous database version had implementation-specific persistence
    # fields. V2.1 intentionally stores versioned analysis metadata instead.
    for column in (
        "document_id", "strategy", "prompt_version", "provider", "model", "status",
        "error_code", "error_message", "created_by_user_id",
    ):
        op.execute(f"ALTER TABLE contract_analyses DROP COLUMN {column} CASCADE")


def downgrade() -> None:
    # Restoring the retired evidence-only model would lose the richer V2.1
    # clauses. Refuse a silent destructive downgrade.
    raise RuntimeError("Downgrading contract_agent_analyzer would discard V2.1 contract clause analyses")
