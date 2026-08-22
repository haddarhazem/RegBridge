"""Add SCRUM-189 immutable assessment snapshots and versions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum189_assessments"
down_revision = "scrum188_project_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_input_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("facts", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessment_snapshots_project_created", "assessment_input_snapshots", ["project_id", "created_at"])
    op.create_table(
        "regulatory_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("result", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_provenance", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("verification_verdict", sa.String(length=30)),
        sa.Column("verification_reasons", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["assessment_input_snapshots.id"]),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_regulatory_assessments_project_version"),
    )
    op.create_index("ix_regulatory_assessments_project_created", "regulatory_assessments", ["project_id", "created_at"])
    op.create_check_constraint("ck_regulatory_assessments_status", "regulatory_assessments", "status IN ('completed', 'blocked', 'failed')")


def downgrade() -> None:
    op.drop_constraint("ck_regulatory_assessments_status", "regulatory_assessments", type_="check")
    op.drop_index("ix_regulatory_assessments_project_created", table_name="regulatory_assessments")
    op.drop_table("regulatory_assessments")
    op.drop_index("ix_assessment_snapshots_project_created", table_name="assessment_input_snapshots")
    op.drop_table("assessment_input_snapshots")
