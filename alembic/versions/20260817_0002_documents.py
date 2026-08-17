"""Create SCRUM-180 document metadata, immutable versions, and jobs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum180_documents"
down_revision = "scrum177_foundation"
branch_labels = None
depends_on = None

uuid_type = postgresql.UUID(as_uuid=True)
timestamp_type = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_user_id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False, server_default="confidential"),
        sa.Column("visibility", sa.String(30), nullable=False, server_default="private"),
        sa.Column("processing_status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("current_version_id", uuid_type),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", timestamp_type),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_documents_owner_user_id_users"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_documents_project_id_projects", ondelete="CASCADE"),
        sa.CheckConstraint("classification IN ('public', 'internal', 'confidential', 'highly_confidential')", name="ck_documents_classification"),
        sa.CheckConstraint("visibility IN ('private', 'project_members', 'shared', 'public')", name="ck_documents_visibility"),
        sa.CheckConstraint("processing_status IN ('uploaded', 'queued', 'processing', 'ready', 'failed', 'quarantined')", name="ck_documents_processing_status"),
    )
    op.create_index("ix_documents_owner_user_id", "documents", ["owner_user_id"])
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])

    op.create_table(
        "document_versions",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", uuid_type, nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("mime_type", sa.String(150), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("malware_scan_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("extracted_text_location", sa.Text),
        sa.Column("extraction_metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("uploaded_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_document_versions"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_document_versions_document_id_documents", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], name="fk_document_versions_uploaded_by_user_id_users"),
        sa.UniqueConstraint("storage_key", name="uq_document_versions_storage_key"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version"),
    )
    op.create_index("ix_document_versions_sha256", "document_versions", ["sha256"])
    op.create_foreign_key(
        "fk_documents_current_version_id_document_versions",
        "documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        "document_processing_jobs",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_version_id", uuid_type, nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", timestamp_type),
        sa.Column("completed_at", timestamp_type),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_document_processing_jobs"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], name="fk_document_processing_jobs_version_id_document_versions", ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_document_processing_jobs_idempotency_key"),
        sa.CheckConstraint("job_type IN ('extract_text', 'classify', 'embed', 'analyze_contract', 'index_research', 'generate_pitch')", name="ck_document_processing_jobs_job_type"),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="ck_document_processing_jobs_status"),
    )


def downgrade() -> None:
    op.drop_table("document_processing_jobs")
    op.drop_constraint("fk_documents_current_version_id_document_versions", "documents", type_="foreignkey")
    op.drop_table("document_versions")
    op.drop_table("documents")
