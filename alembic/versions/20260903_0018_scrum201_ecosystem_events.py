"""Add ecosystem events and traceable participation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum201_ecosystem_events"
down_revision = "scrum200_opportunity_integrity"
branch_labels = None
depends_on = None

def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table("ecosystem_events",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organizer_user_id", u, nullable=False), sa.Column("investor_profile_id", u, nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True), sa.Column("location_type", sa.String(30), nullable=False),
        sa.Column("location_details", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registration_url", sa.Text(), nullable=True), sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ecosystem_events"),
        sa.ForeignKeyConstraint(["organizer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["investor_profile_id"], ["investor_profiles.id"], ondelete="SET NULL"),
        sa.CheckConstraint("event_type IN ('event', 'hackathon', 'webinar', 'call_for_projects')", name="ecosystem_events_event_type"),
        sa.CheckConstraint("location_type IN ('online', 'onsite', 'hybrid')", name="ecosystem_events_location_type"),
        sa.CheckConstraint("status IN ('draft', 'active', 'cancelled')", name="ecosystem_events_status"),
        sa.CheckConstraint("starts_at < ends_at", name="ecosystem_events_valid_dates"),
    )
    op.create_table("event_registrations",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", u, nullable=False), sa.Column("user_id", u, nullable=False), sa.Column("project_id", u, nullable=True),
        sa.Column("status", sa.String(30), server_default="registered", nullable=False), sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_event_registrations"),
        sa.ForeignKeyConstraint(["event_id"], ["ecosystem_events.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_registrations_event_user"), sa.UniqueConstraint("event_id", "user_id", "project_id", name="uq_event_registrations_event_user_project"),
        sa.CheckConstraint("status IN ('interested', 'registered', 'withdrawn')", name="event_registrations_status"),
    )
    op.create_index("ix_ecosystem_events_status_starts", "ecosystem_events", ["status", "starts_at"])
    op.create_index("ix_ecosystem_events_organizer_status", "ecosystem_events", ["organizer_user_id", "status"])
    op.create_index("ix_event_registrations_event_status", "event_registrations", ["event_id", "status"])
    op.create_index("ix_event_registrations_user_status", "event_registrations", ["user_id", "status"])

def downgrade() -> None:
    op.drop_index("ix_event_registrations_user_status", table_name="event_registrations"); op.drop_index("ix_event_registrations_event_status", table_name="event_registrations")
    op.drop_index("ix_ecosystem_events_organizer_status", table_name="ecosystem_events"); op.drop_index("ix_ecosystem_events_status_starts", table_name="ecosystem_events")
    op.drop_table("event_registrations"); op.drop_table("ecosystem_events")
