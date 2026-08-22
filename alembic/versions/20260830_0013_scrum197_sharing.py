"""Add explicit resource-level investor share grants."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum197_sharing"
down_revision = "scrum195_scoring"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "investor_share_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(10), server_default="READ", nullable=False),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("granted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_investor_share_grants"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "recipient_user_id", "resource_type", "resource_id", "resource_version_id", "scope", name="uq_investor_share_grants_exact"),
        sa.CheckConstraint("resource_type IN ('STARTUP_PROFILE_REVISION', 'COMPLIANCE_SCORE_CALCULATION', 'DOCUMENT_VERSION')", name="investor_share_grants_resource_type"),
        sa.CheckConstraint("scope = 'READ'", name="investor_share_grants_scope"),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="investor_share_grants_status"),
    )
    op.create_index("ix_investor_share_grants_recipient_status", "investor_share_grants", ["recipient_user_id", "status"])
    op.create_index("ix_investor_share_grants_project_status", "investor_share_grants", ["project_id", "status"])
    op.create_index("ix_investor_share_grants_resource", "investor_share_grants", ["resource_type", "resource_id", "resource_version_id"])

def downgrade() -> None:
    op.drop_index("ix_investor_share_grants_resource", table_name="investor_share_grants")
    op.drop_index("ix_investor_share_grants_project_status", table_name="investor_share_grants")
    op.drop_index("ix_investor_share_grants_recipient_status", table_name="investor_share_grants")
    op.drop_table("investor_share_grants")
