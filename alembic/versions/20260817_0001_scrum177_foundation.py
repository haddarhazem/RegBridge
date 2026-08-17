"""Create the SCRUM-177 identity, project, membership, and audit foundation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum177_foundation"
down_revision = None
branch_labels = None
depends_on = None

uuid_type = postgresql.UUID(as_uuid=True)
timestamp_type = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("first_name", sa.String(120)),
        sa.Column("last_name", sa.String(120)),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="FR"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("last_login_at", timestamp_type),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("status IN ('active', 'suspended', 'deleted')", name="ck_users_status"),
    )
    op.create_index("ux_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "user_identities",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("email_at_provider", sa.String(320)),
        sa.Column("email_verified_at", timestamp_type),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_user_identities"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_identities_user_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_user_identities_provider_subject"),
    )
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])

    op.create_table(
        "roles",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("role_id", uuid_type, nullable=False),
        sa.Column("assigned_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_roles_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_user_roles_role_id_roles", ondelete="CASCADE"),
    )

    op.create_table(
        "projects",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_user_id", uuid_type, nullable=False),
        sa.Column("project_type", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(255)),
        sa.Column("raw_description", sa.Text, nullable=False),
        sa.Column("user_goal", sa.Text),
        sa.Column("current_progress", sa.String(80)),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="FR"),
        sa.Column("target_market", sa.String(120), nullable=False, server_default="France"),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("visibility", sa.String(30), nullable=False, server_default="private"),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_projects_owner_user_id_users"),
        sa.CheckConstraint("project_type IN ('idea', 'startup_in_creation', 'existing_startup')", name="ck_projects_project_type"),
        sa.CheckConstraint("visibility IN ('private', 'authenticated', 'public')", name="ck_projects_visibility"),
    )
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])
    op.create_index("ix_projects_project_type", "projects", ["project_type"])

    op.create_table(
        "project_members",
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("member_role", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("invited_by_user_id", uuid_type),
        sa.Column("joined_at", timestamp_type),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("project_id", "user_id", name="pk_project_members"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_project_members_project_id_projects", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_project_members_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], name="fk_project_members_invited_by_user_id_users"),
        sa.CheckConstraint("member_role IN ('owner', 'founder', 'admin', 'member', 'viewer')", name="ck_project_members_member_role"),
        sa.CheckConstraint("status IN ('invited', 'active', 'revoked')", name="ck_project_members_status"),
    )
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])
    op.create_index("ix_project_members_project_id_status", "project_members", ["project_id", "status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", uuid_type),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", uuid_type),
        sa.Column("project_id", uuid_type),
        sa.Column("request_id", uuid_type),
        sa.Column("ip_hash", sa.CHAR(64)),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_audit_logs_actor_user_id_users"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_audit_logs_project_id_projects"),
        sa.CheckConstraint("actor_type IN ('anonymous', 'user', 'system', 'admin')", name="ck_audit_logs_actor_type"),
    )
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_logs_project_created", "audit_logs", ["project_id", sa.text("created_at DESC")])
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("user_identities")
    op.drop_table("users")
