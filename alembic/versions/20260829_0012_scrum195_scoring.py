"""Add immutable, versioned compliance score calculations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum195_scoring"
down_revision = "scrum194_compliance"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "compliance_score_calculations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("framework_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("method_key", sa.String(100), nullable=False),
        sa.Column("method_version", sa.String(40), nullable=False),
        sa.Column("evidence_policy_version", sa.String(40), nullable=False),
        sa.Column("rounding_policy", sa.String(80), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("numerator", sa.Integer(), nullable=False),
        sa.Column("denominator", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(8, 2), nullable=True),
        sa.Column("evidence_coverage", sa.Numeric(8, 2), nullable=True),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_score_calculations"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["framework_version_id"], ["compliance_framework_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("denominator >= 0", name="compliance_score_calculations_denominator_nonnegative"),
        sa.CheckConstraint("numerator >= 0", name="compliance_score_calculations_numerator_nonnegative"),
    )
    op.create_index("ix_compliance_score_calculations_project_created", "compliance_score_calculations", ["project_id", "calculated_at"])
    op.create_index("ix_compliance_score_calculations_project_framework", "compliance_score_calculations", ["project_id", "framework_version_id"])

def downgrade() -> None:
    op.drop_index("ix_compliance_score_calculations_project_framework", table_name="compliance_score_calculations")
    op.drop_index("ix_compliance_score_calculations_project_created", table_name="compliance_score_calculations")
    op.drop_table("compliance_score_calculations")
