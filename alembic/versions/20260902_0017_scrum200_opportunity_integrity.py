"""Enforce current opportunity pointers target their own version."""
from alembic import op
import sqlalchemy as sa

revision = "scrum200_opportunity_integrity"
down_revision = "scrum200_investment_opps"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.drop_constraint("fk_investment_opportunities_current_version", "investment_opportunities", type_="foreignkey")
    op.create_unique_constraint("uq_investment_opportunity_versions_id_opportunity", "investment_opportunity_versions", ["id", "opportunity_id"])
    op.create_foreign_key("fk_investment_opportunities_current_version", "investment_opportunities", "investment_opportunity_versions", ["current_version_id", "id"], ["id", "opportunity_id"], ondelete="RESTRICT")

def downgrade() -> None:
    op.drop_constraint("fk_investment_opportunities_current_version", "investment_opportunities", type_="foreignkey")
    op.drop_constraint("uq_investment_opportunity_versions_id_opportunity", "investment_opportunity_versions", type_="unique")
    op.create_foreign_key("fk_investment_opportunities_current_version", "investment_opportunities", "investment_opportunity_versions", ["current_version_id"], ["id"], ondelete="RESTRICT")
