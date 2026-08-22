"""Add explicit creation/compliance purpose to SCRUM-190 roadmaps."""

from alembic import op
import sqlalchemy as sa


revision = "scrum191_roadmap_purpose"
down_revision = "scrum190_roadmaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("launch_roadmaps", sa.Column("purpose", sa.String(length=20), server_default="creation", nullable=False))
    op.create_check_constraint("launch_roadmaps_purpose", "launch_roadmaps", "purpose IN ('creation', 'compliance')")


def downgrade() -> None:
    op.drop_constraint("launch_roadmaps_purpose", "launch_roadmaps", type_="check")
    op.drop_column("launch_roadmaps", "purpose")
