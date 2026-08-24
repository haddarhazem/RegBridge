"""Persist SCRUM-205 investor brief verification runs and claim verdicts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum205_brief_verification"
down_revision = "scrum204_briefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.drop_constraint("ck_investor_opportunity_brief_status", "investor_opportunity_brief_runs", type_="check")
    op.create_check_constraint("ck_investor_opportunity_brief_status", "investor_opportunity_brief_runs", "status IN ('DRAFT', 'UNVERIFIED', 'VERIFIED', 'VERIFICATION_FAILED')")
    op.create_table(
        "investor_opportunity_brief_verification_runs",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("brief_run_id", u, nullable=False),
        sa.Column("verifier_strategy", sa.String(60), nullable=False),
        sa.Column("verifier_version", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("model", sa.String(120)),
        sa.Column("prompt_version", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_brief_verification_runs"),
        sa.ForeignKeyConstraint(["brief_run_id"], ["investor_opportunity_brief_runs.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('VERIFIED', 'VERIFICATION_FAILED')", name="ck_brief_verification_run_status"),
    )
    op.create_index("ix_brief_verification_runs_brief_created", "investor_opportunity_brief_verification_runs", ["brief_run_id", sa.text("created_at DESC")])
    op.create_table(
        "investor_opportunity_brief_claim_verifications",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("verification_run_id", u, nullable=False),
        sa.Column("claim_id", sa.String(120), nullable=False),
        sa.Column("section", sa.String(80), nullable=False),
        sa.Column("claim_text", sa.String(1200), nullable=False),
        sa.Column("claim_type", sa.String(80), nullable=False),
        sa.Column("verdict", sa.String(30), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_brief_claim_verifications"),
        sa.ForeignKeyConstraint(["verification_run_id"], ["investor_opportunity_brief_verification_runs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("verdict IN ('SUPPORTED', 'UNSUPPORTED', 'UNVERIFIABLE')", name="ck_brief_claim_verdict"),
    )
    op.create_index("ix_brief_claim_verifications_run", "investor_opportunity_brief_claim_verifications", ["verification_run_id"])


def downgrade() -> None:
    op.drop_index("ix_brief_claim_verifications_run", table_name="investor_opportunity_brief_claim_verifications")
    op.drop_table("investor_opportunity_brief_claim_verifications")
    op.drop_index("ix_brief_verification_runs_brief_created", table_name="investor_opportunity_brief_verification_runs")
    op.drop_table("investor_opportunity_brief_verification_runs")
    op.drop_constraint("ck_investor_opportunity_brief_status", "investor_opportunity_brief_runs", type_="check")
    op.create_check_constraint("ck_investor_opportunity_brief_status", "investor_opportunity_brief_runs", "status IN ('DRAFT', 'UNVERIFIED')")
