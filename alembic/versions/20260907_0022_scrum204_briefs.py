"""Persist SCRUM-204 investor opportunity brief generations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum204_briefs"
down_revision = "scrum203_matching_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "investor_opportunity_brief_runs",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("investor_user_id", u, nullable=False),
        sa.Column("investor_thesis_version_id", u, nullable=False),
        sa.Column("startup_project_id", u, nullable=False),
        sa.Column("matching_run_id", u, nullable=True),
        sa.Column("startup_snapshot_revision_id", u, nullable=True),
        sa.Column("investor_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("startup_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_bundle", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matching_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generation_strategy", sa.String(60), nullable=False),
        sa.Column("generation_version", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("model", sa.String(120)),
        sa.Column("prompt_version", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_investor_opportunity_brief_runs"),
        sa.ForeignKeyConstraint(["investor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["investor_thesis_version_id"], ["investor_thesis_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["startup_project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["matching_run_id"], ["investment_matching_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["startup_snapshot_revision_id"], ["startup_profile_revisions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('DRAFT', 'UNVERIFIED')", name="ck_investor_opportunity_brief_status"),
    )
    op.create_index("ix_investor_opportunity_brief_runs_investor_created", "investor_opportunity_brief_runs", ["investor_user_id", sa.text("created_at DESC")])
    op.create_index("ix_investor_opportunity_brief_runs_startup_created", "investor_opportunity_brief_runs", ["startup_project_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_investor_opportunity_brief_runs_startup_created", table_name="investor_opportunity_brief_runs")
    op.drop_index("ix_investor_opportunity_brief_runs_investor_created", table_name="investor_opportunity_brief_runs")
    op.drop_table("investor_opportunity_brief_runs")
