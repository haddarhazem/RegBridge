"""Prevent concurrent duplicate active exact share grants."""
from alembic import op
import sqlalchemy as sa

revision = "scrum197_grant_uniqueness"
down_revision = "scrum197_sharing"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_index("ux_investor_share_grants_active_exact", "investor_share_grants", ["project_id", "recipient_user_id", "resource_type", "resource_id", sa.text("coalesce(resource_version_id, '00000000-0000-0000-0000-000000000000'::uuid)"), "scope"], unique=True, postgresql_where=sa.text("status = 'ACTIVE'"))

def downgrade() -> None:
    op.drop_index("ux_investor_share_grants_active_exact", table_name="investor_share_grants")
