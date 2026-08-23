"""Add versioned investment opportunities."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum200_investment_opps"
down_revision = "scrum198_investor_thesis"
branch_labels = None
depends_on = None

def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table("investment_opportunities",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("investor_profile_id", u, nullable=False),
        sa.Column("current_version_id", u, nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("opportunity_type", sa.String(60), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("visibility", sa.String(30), server_default="AUTHENTICATED", nullable=False),
        sa.Column("status", sa.String(30), server_default="DRAFT", nullable=False),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_investment_opportunities"),
        sa.ForeignKeyConstraint(["investor_profile_id"], ["investor_profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')", name="investment_opportunities_status"),
        sa.CheckConstraint("visibility IN ('AUTHENTICATED', 'PUBLIC')", name="investment_opportunities_visibility"),
    )
    op.create_table("investment_opportunity_versions",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("opportunity_id", u, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("opportunity_type", sa.String(60), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("visibility", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", u, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_investment_opportunity_versions"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["investment_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("opportunity_id", "version_number", name="uq_investment_opportunity_versions_number"),
        sa.CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')", name="investment_opportunity_versions_status"),
    )
    op.create_foreign_key("fk_investment_opportunities_current_version", "investment_opportunities", "investment_opportunity_versions", ["current_version_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_investment_opportunities_investor_status", "investment_opportunities", ["investor_profile_id", "status"])
    op.create_index("ix_investment_opportunity_versions_opportunity_created", "investment_opportunity_versions", ["opportunity_id", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_investment_opportunity_versions_opportunity_created", table_name="investment_opportunity_versions")
    op.drop_index("ix_investment_opportunities_investor_status", table_name="investment_opportunities")
    op.drop_constraint("fk_investment_opportunities_current_version", "investment_opportunities", type_="foreignkey")
    op.drop_table("investment_opportunity_versions")
    op.drop_table("investment_opportunities")
