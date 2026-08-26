"""Add version-bound research access requests and reuse share grants."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum212_research_access"
down_revision = "scrum211_uncertainty"
branch_labels = None
depends_on = None
u = postgresql.UUID(as_uuid=True)

def upgrade() -> None:
    op.create_table(
        "research_access_requests",
        sa.Column("id", u, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("research_output_id", u, nullable=False),
        sa.Column("research_output_version_id", u),
        sa.Column("research_discovery_version_id", u),
        sa.Column("requester_user_id", u, nullable=False),
        sa.Column("requester_project_id", u),
        sa.Column("requested_scopes", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("granted_scopes", postgresql.JSONB),
        sa.Column("message", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("decided_by_user_id", u),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["research_output_id"], ["research_outputs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_output_version_id"], ["research_output_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["research_discovery_version_id"], ["research_discovery_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requester_project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('PENDING', 'ACCEPTED', 'LIMITED', 'REFUSED', 'REVOKED')", name="research_access_requests_status"),
    )
    op.create_index("ix_research_access_requests_output_status", "research_access_requests", ["research_output_id", "status"])
    op.create_index("ix_research_access_requests_requester_created", "research_access_requests", ["requester_user_id", "created_at"])
    op.drop_constraint("investor_share_grants_resource_type", "investor_share_grants", type_="check")
    op.drop_constraint("investor_share_grants_scope", "investor_share_grants", type_="check")
    op.create_check_constraint("investor_share_grants_resource_type", "investor_share_grants", "resource_type IN ('STARTUP_PROFILE_REVISION', 'COMPLIANCE_SCORE_CALCULATION', 'DOCUMENT_VERSION', 'INVESTOR_OPPORTUNITY_BRIEF_VERSION', 'RESEARCH_OUTPUT_VERSION', 'RESEARCH_DISCOVERY_VERSION')")
    op.create_check_constraint("investor_share_grants_scope", "investor_share_grants", "scope IN ('READ', 'CONTACT', 'DISCOVERY_READ', 'FULL_DOCUMENT_READ', 'COLLABORATION')")
    op.alter_column("investor_share_grants", "scope", type_=sa.String(30), existing_type=sa.String(10), existing_nullable=False, existing_server_default=sa.text("'READ'::character varying"))
    op.add_column("investor_share_grants", sa.Column("request_id", u))
    op.create_foreign_key("fk_investor_share_grants_request_id", "investor_share_grants", "research_access_requests", ["request_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_investor_share_grants_request", "investor_share_grants", ["request_id", "status"])

def downgrade() -> None:
    op.drop_index("ix_investor_share_grants_request", table_name="investor_share_grants")
    op.drop_constraint("fk_investor_share_grants_request_id", "investor_share_grants", type_="foreignkey")
    op.drop_column("investor_share_grants", "request_id")
    op.alter_column("investor_share_grants", "scope", type_=sa.String(10), existing_type=sa.String(30), existing_nullable=False, existing_server_default=sa.text("'READ'::character varying"))
    op.drop_constraint("investor_share_grants_scope", "investor_share_grants", type_="check")
    op.drop_constraint("investor_share_grants_resource_type", "investor_share_grants", type_="check")
    op.create_check_constraint("investor_share_grants_resource_type", "investor_share_grants", "resource_type IN ('STARTUP_PROFILE_REVISION', 'COMPLIANCE_SCORE_CALCULATION', 'DOCUMENT_VERSION', 'INVESTOR_OPPORTUNITY_BRIEF_VERSION')")
    op.create_check_constraint("investor_share_grants_scope", "investor_share_grants", "scope = 'READ'")
    op.drop_index("ix_research_access_requests_requester_created", table_name="research_access_requests")
    op.drop_index("ix_research_access_requests_output_status", table_name="research_access_requests")
    op.drop_table("research_access_requests")
