"""Add consent-scoped contact requests."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum202_contact_requests"
down_revision = "scrum201_ecosystem_events"
branch_labels = None
depends_on = None

def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table("contact_requests",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("requester_user_id", u, nullable=False), sa.Column("source_project_id", u, nullable=True), sa.Column("target_type", sa.String(40), nullable=False), sa.Column("target_id", u, nullable=False), sa.Column("message", sa.Text(), nullable=True), sa.Column("status", sa.String(30), server_default="pending", nullable=False), sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contact_requests"), sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_project_id"], ["projects.id"], ondelete="CASCADE"), sa.CheckConstraint("target_type IN ('project', 'investor_profile', 'researcher_profile', 'research_output')", name="contact_requests_target_type"), sa.CheckConstraint("status IN ('pending', 'accepted', 'declined', 'cancelled')", name="contact_requests_status"))
    op.create_table("contact_points",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("owner_user_id", u, nullable=False), sa.Column("project_id", u, nullable=True), sa.Column("channel", sa.String(30), nullable=False), sa.Column("value", sa.Text(), nullable=False), sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contact_points"), sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"), sa.CheckConstraint("channel IN ('EMAIL', 'WEBSITE')", name="contact_points_channel"))
    op.create_table("contact_consents",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("request_id", u, nullable=False), sa.Column("contact_point_id", u, nullable=False), sa.Column("granted_by_user_id", u, nullable=False), sa.Column("channel", sa.String(30), nullable=False), sa.Column("value_snapshot", sa.Text(), nullable=False), sa.Column("status", sa.String(30), server_default="active", nullable=False), sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contact_consents"), sa.ForeignKeyConstraint(["request_id"], ["contact_requests.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["contact_point_id"], ["contact_points.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.CheckConstraint("status IN ('active', 'revoked')", name="contact_consents_status"), sa.UniqueConstraint("request_id", "contact_point_id", "status", name="uq_contact_consents_request_point_status"))
    op.create_index("ix_contact_requests_requester_status", "contact_requests", ["requester_user_id", "status"]); op.create_index("ix_contact_requests_target", "contact_requests", ["target_type", "target_id", "status"]); op.create_index("ux_contact_requests_pending", "contact_requests", ["requester_user_id", "target_type", "target_id", "source_project_id"], unique=True, postgresql_where=sa.text("status = 'pending'"))
    op.create_index("ix_contact_points_owner_active", "contact_points", ["owner_user_id", "active"]); op.create_index("ix_contact_consents_request_status", "contact_consents", ["request_id", "status"])

def downgrade() -> None:
    op.drop_index("ix_contact_consents_request_status", table_name="contact_consents"); op.drop_index("ix_contact_points_owner_active", table_name="contact_points"); op.drop_index("ux_contact_requests_pending", table_name="contact_requests"); op.drop_index("ix_contact_requests_target", table_name="contact_requests"); op.drop_index("ix_contact_requests_requester_status", table_name="contact_requests"); op.drop_table("contact_consents"); op.drop_table("contact_points"); op.drop_table("contact_requests")
