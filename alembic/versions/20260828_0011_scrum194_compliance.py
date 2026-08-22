"""Add versioned compliance frameworks, project controls and evidence."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum194_compliance"
down_revision = "scrum193_contract_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table("compliance_frameworks",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("stable_key", sa.String(80), nullable=False), sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_frameworks"), sa.UniqueConstraint("stable_key", name="uq_compliance_frameworks_stable_key"))
    op.create_table("compliance_framework_versions",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("framework_id", uuid_type, nullable=False), sa.Column("version_identifier", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False), sa.Column("effective_date", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_framework_versions"), sa.ForeignKeyConstraint(["framework_id"], ["compliance_frameworks.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("framework_id", "version_identifier", name="uq_compliance_framework_versions_identifier"), sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="compliance_framework_versions_status"))
    op.create_index("ix_compliance_framework_versions_framework_status", "compliance_framework_versions", ["framework_id", "status"])
    op.create_table("compliance_control_definitions",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("framework_version_id", uuid_type, nullable=False),
        sa.Column("stable_key", sa.String(120), nullable=False), sa.Column("title", sa.String(300), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(120)), sa.Column("source_references", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False), sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_control_definitions"), sa.ForeignKeyConstraint(["framework_version_id"], ["compliance_framework_versions.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("framework_version_id", "stable_key", name="uq_compliance_control_definitions_version_key"))
    op.create_index("ix_compliance_control_definitions_version_order", "compliance_control_definitions", ["framework_version_id", "display_order"])
    op.create_table("project_framework_adoptions",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("project_id", uuid_type, nullable=False), sa.Column("framework_version_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False), sa.Column("adopted_by_user_id", uuid_type, nullable=False), sa.Column("adopted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name="pk_project_framework_adoptions"), sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["framework_version_id"], ["compliance_framework_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["adopted_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("project_id", "framework_version_id", name="uq_project_framework_adoptions_version"), sa.CheckConstraint("status IN ('active', 'superseded')", name="project_framework_adoptions_status"))
    op.create_index("ix_project_framework_adoptions_project_status", "project_framework_adoptions", ["project_id", "status"])
    op.create_table("project_compliance_controls",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("project_id", uuid_type, nullable=False), sa.Column("framework_version_id", uuid_type, nullable=False), sa.Column("control_definition_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(20), server_default="NOT_STARTED", nullable=False), sa.Column("applicability", sa.String(20), server_default="UNDECIDED", nullable=False), sa.Column("notes", sa.Text()), sa.Column("created_by_user_id", uuid_type, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_project_compliance_controls"), sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["framework_version_id"], ["compliance_framework_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["control_definition_id"], ["compliance_control_definitions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("project_id", "control_definition_id", name="uq_project_compliance_controls_definition"), sa.CheckConstraint("status IN ('NOT_STARTED', 'IN_PROGRESS', 'SATISFIED', 'NOT_SATISFIED')", name="project_compliance_controls_status"), sa.CheckConstraint("applicability IN ('APPLICABLE', 'NOT_APPLICABLE', 'UNDECIDED')", name="project_compliance_controls_applicability"))
    op.create_index("ix_project_compliance_controls_project_framework", "project_compliance_controls", ["project_id", "framework_version_id"])
    op.create_table("compliance_evidence",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("project_id", uuid_type, nullable=False), sa.Column("document_version_id", uuid_type), sa.Column("declaration_type", sa.String(100)), sa.Column("declaration_value", sa.String(1000)), sa.Column("declaration_note", sa.Text()), sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False), sa.Column("created_by_user_id", uuid_type, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("revoked_by_user_id", uuid_type), sa.Column("revocation_reason", sa.String(500)),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_evidence"), sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]), sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"]),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="compliance_evidence_status"), sa.CheckConstraint("(document_version_id IS NOT NULL AND declaration_type IS NULL AND declaration_value IS NULL) OR (document_version_id IS NULL AND declaration_type IS NOT NULL AND declaration_value IS NOT NULL)", name="compliance_evidence_kind"))
    op.create_index("ix_compliance_evidence_project_status", "compliance_evidence", ["project_id", "status"])
    op.create_table("compliance_control_evidence_links",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False), sa.Column("project_control_id", uuid_type, nullable=False), sa.Column("evidence_id", uuid_type, nullable=False), sa.Column("attached_by_user_id", uuid_type, nullable=False), sa.Column("attached_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_control_evidence_links"), sa.ForeignKeyConstraint(["project_control_id"], ["project_compliance_controls.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["evidence_id"], ["compliance_evidence.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["attached_by_user_id"], ["users.id"]), sa.UniqueConstraint("project_control_id", "evidence_id", name="uq_compliance_control_evidence_link"))
    op.create_index("ix_compliance_control_evidence_links_control", "compliance_control_evidence_links", ["project_control_id"])
    op.execute("INSERT INTO compliance_frameworks (stable_key, name) VALUES ('GDPR', 'GDPR / RGPD'), ('EU_AI_ACT', 'EU AI Act')")
    op.execute("INSERT INTO compliance_framework_versions (framework_id, version_identifier, status) SELECT id, 'baseline', 'active' FROM compliance_frameworks WHERE stable_key IN ('GDPR', 'EU_AI_ACT')")


def downgrade() -> None:
    op.drop_index("ix_compliance_control_evidence_links_control", table_name="compliance_control_evidence_links")
    op.drop_table("compliance_control_evidence_links")
    op.drop_index("ix_compliance_evidence_project_status", table_name="compliance_evidence")
    op.drop_table("compliance_evidence")
    op.drop_index("ix_project_compliance_controls_project_framework", table_name="project_compliance_controls")
    op.drop_table("project_compliance_controls")
    op.drop_index("ix_project_framework_adoptions_project_status", table_name="project_framework_adoptions")
    op.drop_table("project_framework_adoptions")
    op.drop_index("ix_compliance_control_definitions_version_order", table_name="compliance_control_definitions")
    op.drop_table("compliance_control_definitions")
    op.drop_index("ix_compliance_framework_versions_framework_status", table_name="compliance_framework_versions")
    op.drop_table("compliance_framework_versions")
    op.drop_table("compliance_frameworks")
