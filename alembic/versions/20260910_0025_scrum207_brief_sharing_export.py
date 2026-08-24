"""Allow exact approved brief versions to use the existing sharing grants."""

from alembic import op
import sqlalchemy as sa


revision = "scrum207_brief_sharing_export"
down_revision = "scrum206_brief_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("investor_share_grants_resource_type", "investor_share_grants", type_="check")
    op.create_check_constraint(
        "investor_share_grants_resource_type",
        "investor_share_grants",
        "resource_type IN ('STARTUP_PROFILE_REVISION', 'COMPLIANCE_SCORE_CALCULATION', 'DOCUMENT_VERSION', 'INVESTOR_OPPORTUNITY_BRIEF_VERSION')",
    )


def downgrade() -> None:
    op.drop_constraint("investor_share_grants_resource_type", "investor_share_grants", type_="check")
    op.create_check_constraint(
        "investor_share_grants_resource_type",
        "investor_share_grants",
        "resource_type IN ('STARTUP_PROFILE_REVISION', 'COMPLIANCE_SCORE_CALCULATION', 'DOCUMENT_VERSION')",
    )
