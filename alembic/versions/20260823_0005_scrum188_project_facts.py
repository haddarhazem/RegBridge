"""Add SCRUM-188 project facts with provenance and confirmation state."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum188_project_facts"
down_revision = "scrum187_idea_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(length=30), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("origin", sa.String(length=30), server_default="inferred", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending_confirmation", nullable=False),
        sa.Column("provenance", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("uncertainty", sa.String(length=10), server_default="high", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "domain", "value", "status", name="uq_project_facts_active_value"),
    )
    op.create_index("ix_project_facts_project_status", "project_facts", ["project_id", "status"])
    op.create_check_constraint("ck_project_facts_origin", "project_facts", "origin IN ('inferred', 'user_declared')")
    op.create_check_constraint("ck_project_facts_status", "project_facts", "status IN ('pending_confirmation', 'confirmed', 'corrected', 'deleted')")
    op.create_check_constraint("ck_project_facts_uncertainty", "project_facts", "uncertainty IN ('high', 'medium', 'low')")
    op.create_check_constraint("ck_project_facts_domain", "project_facts", "domain IN ('activity', 'sector', 'technology', 'data', 'market', 'location')")


def downgrade() -> None:
    op.drop_constraint("ck_project_facts_domain", "project_facts", type_="check")
    op.drop_constraint("ck_project_facts_uncertainty", "project_facts", type_="check")
    op.drop_constraint("ck_project_facts_status", "project_facts", type_="check")
    op.drop_constraint("ck_project_facts_origin", "project_facts", type_="check")
    op.drop_index("ix_project_facts_project_status", table_name="project_facts")
    op.drop_table("project_facts")
