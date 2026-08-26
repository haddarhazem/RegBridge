"""Persist deterministic SCRUM-211 uncertainty codes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum211_uncertainty"
down_revision = "scrum211_matching"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("research_match_results", sa.Column("uncertainty_codes", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))

def downgrade():
    op.drop_column("research_match_results", "uncertainty_codes")
