"""Create field-level startup profile visibility and immutable revisions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum192_startup_profiles"
down_revision = "scrum191_roadmap_purpose"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "startup_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_startup_profiles"),
        sa.UniqueConstraint("project_id", name="uq_startup_profiles_project_id"),
    )
    op.create_table(
        "startup_profile_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("section", sa.String(length=50), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("visibility IN ('PUBLIC', 'INVESTOR_SHARED', 'PRIVATE')", name="startup_profile_fields_visibility"),
        sa.ForeignKeyConstraint(["profile_id"], ["startup_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_startup_profile_fields"),
        sa.UniqueConstraint("profile_id", "field_name", name="uq_startup_profile_fields_name"),
    )
    op.create_index("ix_startup_profile_fields_profile_visibility", "startup_profile_fields", ["profile_id", "visibility"])
    op.create_table(
        "startup_profile_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["startup_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_startup_profile_revisions"),
        sa.UniqueConstraint("profile_id", "revision_number", name="uq_startup_profile_revisions_number"),
    )
    op.create_index("ix_startup_profile_revisions_profile_created", "startup_profile_revisions", ["profile_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_startup_profile_revisions_profile_created", table_name="startup_profile_revisions")
    op.drop_table("startup_profile_revisions")
    op.drop_index("ix_startup_profile_fields_profile_visibility", table_name="startup_profile_fields")
    op.drop_table("startup_profile_fields")
    op.drop_table("startup_profiles")
