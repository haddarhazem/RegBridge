"""Persist authorized investor-startup matching snapshots and reports."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum203_matching_runs"
down_revision = "scrum202_pending_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table("investment_matching_runs",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("investor_user_id", u, nullable=False), sa.Column("investor_thesis_version_id", u, nullable=False), sa.Column("startup_project_id", u, nullable=False), sa.Column("startup_snapshot_revision_id", u, nullable=True),
        sa.Column("investor_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False), sa.Column("startup_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matching_method", sa.String(80), nullable=False), sa.Column("matching_method_version", sa.String(30), nullable=False), sa.Column("score", sa.Numeric(8, 6)), sa.Column("score_formula", sa.String(255), nullable=False), sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False), sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation_mode", sa.String(40), server_default="deterministic_fallback", nullable=False), sa.Column("llm_provider", sa.String(80)), sa.Column("llm_model", sa.String(120)), sa.Column("prompt_version", sa.String(80)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_investment_matching_runs"), sa.ForeignKeyConstraint(["investor_user_id"], ["users.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["investor_thesis_version_id"], ["investor_thesis_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["startup_project_id"], ["projects.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["startup_snapshot_revision_id"], ["startup_profile_revisions.id"], ondelete="RESTRICT"))
    op.create_index("ix_investment_matching_runs_investor_created", "investment_matching_runs", ["investor_user_id", sa.text("created_at DESC")])
    op.create_index("ix_investment_matching_runs_startup", "investment_matching_runs", ["startup_project_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_investment_matching_runs_startup", table_name="investment_matching_runs")
    op.drop_index("ix_investment_matching_runs_investor_created", table_name="investment_matching_runs")
    op.drop_table("investment_matching_runs")
