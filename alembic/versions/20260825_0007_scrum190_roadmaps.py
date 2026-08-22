"""Add SCRUM-190 versioned launch roadmaps."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum190_roadmaps"
down_revision = "scrum189_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "launch_roadmaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("regulatory_assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["regulatory_assessment_id"], ["regulatory_assessments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_launch_roadmaps_project_version"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="launch_roadmaps_status"),
    )
    op.create_index("ix_launch_roadmaps_project_created", "launch_roadmaps", ["project_id", "created_at"])
    op.create_table(
        "launch_roadmap_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("roadmap_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("justification", sa.String(length=2000), nullable=False),
        sa.Column("priority_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("source_conclusion_refs", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("dependency_item_refs", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["roadmap_id"], ["launch_roadmaps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("item_type IN ('obligation', 'recommendation', 'uncertainty')", name="launch_roadmap_items_type"),
        sa.CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'skipped')", name="launch_roadmap_items_status"),
    )
    op.create_index("ix_launch_roadmap_items_roadmap_order", "launch_roadmap_items", ["roadmap_id", "priority_order"])


def downgrade() -> None:
    op.drop_index("ix_launch_roadmap_items_roadmap_order", table_name="launch_roadmap_items")
    op.drop_table("launch_roadmap_items")
    op.drop_index("ix_launch_roadmaps_project_created", table_name="launch_roadmaps")
    op.drop_table("launch_roadmaps")
