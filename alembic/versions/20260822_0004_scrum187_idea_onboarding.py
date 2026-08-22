"""Add contextual idea-project onboarding state for SCRUM-187."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum187_idea_onboarding"
down_revision = "scrum182_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("projects", "target_market", existing_type=sa.String(120), nullable=True, server_default=None)
    op.add_column("projects", sa.Column("activity", sa.String(500), nullable=True))
    op.add_column("projects", sa.Column("sector", sa.String(160), nullable=True))
    op.add_column("projects", sa.Column("technology", sa.String(500), nullable=True))
    op.add_column("projects", sa.Column("data_context", sa.String(500), nullable=True))
    op.add_column("projects", sa.Column("location", sa.String(160), nullable=True))
    op.add_column("projects", sa.Column("onboarding_status", sa.String(30), nullable=False, server_default="in_progress"))
    op.add_column("projects", sa.Column("confirmed_fields", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_check_constraint("ck_projects_onboarding_status", "projects", "onboarding_status IN ('in_progress', 'complete')")


def downgrade() -> None:
    op.drop_constraint("ck_projects_onboarding_status", "projects", type_="check")
    op.drop_column("projects", "confirmed_fields")
    op.drop_column("projects", "onboarding_status")
    op.drop_column("projects", "location")
    op.drop_column("projects", "data_context")
    op.drop_column("projects", "technology")
    op.drop_column("projects", "sector")
    op.drop_column("projects", "activity")
    op.alter_column("projects", "target_market", existing_type=sa.String(120), nullable=False, server_default="France")
