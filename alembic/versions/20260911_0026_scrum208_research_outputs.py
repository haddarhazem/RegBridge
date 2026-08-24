"""Create private researcher profiles and immutable research output versions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum208_research_outputs"
down_revision = "scrum207_brief_sharing_export"
branch_labels = None
depends_on = None

uuid_type = postgresql.UUID(as_uuid=True)
timestamp_type = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "researcher_profiles",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("affiliation", sa.String(255)),
        sa.Column("scientific_domains", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_researcher_profiles_user_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_researcher_profiles_user_id"),
    )
    op.create_index("ix_researcher_profiles_user_id", "researcher_profiles", ["user_id"])

    op.create_table(
        "research_outputs",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("researcher_profile_id", uuid_type, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("authors", postgresql.JSONB, nullable=False),
        sa.Column("rights_holder", sa.String(500)),
        sa.Column("licence", sa.String(255)),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="private"),
        sa.Column("rights_metadata_status", sa.String(20), nullable=False, server_default="INCOMPLETE"),
        sa.Column("publication_ready", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["researcher_profile_id"], ["researcher_profiles.id"], name="fk_research_outputs_profile_id_profiles", ondelete="CASCADE"),
        sa.CheckConstraint("visibility IN ('private', 'public')", name="research_outputs_visibility"),
        sa.CheckConstraint("rights_metadata_status IN ('COMPLETE', 'INCOMPLETE')", name="research_outputs_rights_status"),
    )
    op.create_index("ix_research_outputs_profile_created", "research_outputs", ["researcher_profile_id", "created_at"])

    op.create_table(
        "research_output_versions",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("research_output_id", uuid_type, nullable=False),
        sa.Column("document_version_id", uuid_type, nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("uploaded_by_user_id", uuid_type, nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["research_output_id"], ["research_outputs.id"], name="fk_research_output_versions_output_id_outputs", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], name="fk_research_output_versions_document_version_id_versions", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], name="fk_research_output_versions_uploaded_by_users"),
        sa.UniqueConstraint("research_output_id", "version_number", name="uq_research_output_versions_number"),
        sa.UniqueConstraint("document_version_id", name="uq_research_output_versions_document_version"),
        sa.CheckConstraint("version_number > 0", name="research_output_versions_positive_number"),
        sa.CheckConstraint("length(content_hash) = 64", name="research_output_versions_hash_length"),
    )
    op.create_index("ix_research_output_versions_output_created", "research_output_versions", ["research_output_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_research_output_versions_output_created", table_name="research_output_versions")
    op.drop_table("research_output_versions")
    op.drop_index("ix_research_outputs_profile_created", table_name="research_outputs")
    op.drop_table("research_outputs")
    op.drop_index("ix_researcher_profiles_user_id", table_name="researcher_profiles")
    op.drop_table("researcher_profiles")
