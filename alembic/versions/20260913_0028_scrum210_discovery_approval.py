"""Add versioned, author-approved research discovery snapshots."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum210_discovery_approval"
down_revision = "scrum209_research_extraction"
branch_labels = None
depends_on = None
uuid_type = postgresql.UUID(as_uuid=True)
ts = sa.DateTime(timezone=True)

def upgrade() -> None:
    op.create_table("research_discoveries",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("research_output_id", uuid_type, nullable=False), sa.Column("owner_user_id", uuid_type, nullable=False),
        sa.Column("created_at", ts, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["research_output_id"], ["research_outputs.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]), sa.UniqueConstraint("research_output_id", name="uq_research_discoveries_output"))
    op.create_table("research_discovery_versions",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")), sa.Column("discovery_id", uuid_type, nullable=False), sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("extraction_run_id", uuid_type, nullable=False), sa.Column("research_output_version_id", uuid_type, nullable=False), sa.Column("document_version_id", uuid_type, nullable=False), sa.Column("source_sha256", sa.CHAR(64), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False), sa.Column("visibility", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("approved_by_user_id", uuid_type), sa.Column("approved_at", ts), sa.Column("created_at", ts, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["discovery_id"], ["research_discoveries.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["extraction_run_id"], ["research_extraction_runs.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["research_output_version_id"], ["research_output_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]), sa.UniqueConstraint("discovery_id", "version_number", name="uq_research_discovery_versions_number"), sa.CheckConstraint("status IN ('DRAFT', 'APPROVED')", name="research_discovery_versions_status"))
    op.create_index("ix_research_discovery_versions_current", "research_discovery_versions", ["discovery_id", "version_number"])

def downgrade() -> None:
    op.drop_index("ix_research_discovery_versions_current", table_name="research_discovery_versions"); op.drop_table("research_discovery_versions"); op.drop_table("research_discoveries")
