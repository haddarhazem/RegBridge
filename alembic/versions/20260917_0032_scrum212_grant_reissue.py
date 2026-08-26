"""Allow a new request to reissue a previously revoked research grant."""
from alembic import op

revision = "scrum212_grant_reissue"
down_revision = "scrum212_research_access"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.drop_constraint("uq_investor_share_grants_exact", "investor_share_grants", type_="unique")

def downgrade() -> None:
    op.create_unique_constraint("uq_investor_share_grants_exact", "investor_share_grants", ["project_id", "recipient_user_id", "resource_type", "resource_id", "resource_version_id", "scope"])
