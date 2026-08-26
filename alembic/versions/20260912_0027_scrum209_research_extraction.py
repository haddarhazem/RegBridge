"""Add immutable research extraction runs and evidence."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum209_research_extraction"
down_revision = "scrum208_research_outputs"
branch_labels = None
depends_on = None
uuid_type = postgresql.UUID(as_uuid=True)
timestamp_type = sa.DateTime(timezone=True)
fields = "'domains','technologies','research_problem','methodology','main_results','explicit_applications','keywords','limitations'"


def upgrade() -> None:
    op.create_table("research_extraction_runs",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_user_id", uuid_type, nullable=False), sa.Column("research_output_id", uuid_type, nullable=False),
        sa.Column("research_output_version_id", uuid_type, nullable=False), sa.Column("document_version_id", uuid_type, nullable=False),
        sa.Column("source_sha256", sa.CHAR(64), nullable=False), sa.Column("strategy", sa.String(80), nullable=False),
        sa.Column("strategy_version", sa.String(30), nullable=False), sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False), sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("schema_version", sa.String(30), nullable=False), sa.Column("segmenter_version", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("regbridge_abstract", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")), sa.Column("completed_at", timestamp_type),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]), sa.ForeignKeyConstraint(["research_output_id"], ["research_outputs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_output_version_id"], ["research_output_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("strategy = 'extractive_evidence_locked'", name="research_extraction_runs_strategy"),
        sa.CheckConstraint("status IN ('GENERATED', 'FAILED')", name="research_extraction_runs_status"),
    )
    op.create_index("ix_research_extraction_runs_version_created", "research_extraction_runs", ["research_output_version_id", "created_at"])
    op.create_table("research_extraction_items",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")), sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("field", sa.String(40), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("source_text", sa.Text), sa.Column("item_order", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["research_extraction_runs.id"], ondelete="CASCADE"), sa.CheckConstraint(f"field IN ({fields})", name="research_extraction_items_field"), sa.CheckConstraint("status IN ('SUPPORTED', 'NOT_AVAILABLE')", name="research_extraction_items_status"),
    )
    op.create_index("ix_research_extraction_items_run_field", "research_extraction_items", ["run_id", "field"])
    op.create_table("research_evidence_refs",
        sa.Column("id", uuid_type, primary_key=True, server_default=sa.text("gen_random_uuid()")), sa.Column("item_id", uuid_type, nullable=False),
        sa.Column("research_output_version_id", uuid_type, nullable=False), sa.Column("document_version_id", uuid_type, nullable=False), sa.Column("segment_id", sa.String(40), nullable=False), sa.Column("locator", postgresql.JSONB, nullable=False), sa.Column("item_order", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["research_extraction_items.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["research_output_version_id"], ["research_output_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_research_evidence_refs_item_order", "research_evidence_refs", ["item_id", "item_order"])


def downgrade() -> None:
    op.drop_index("ix_research_evidence_refs_item_order", table_name="research_evidence_refs"); op.drop_table("research_evidence_refs")
    op.drop_index("ix_research_extraction_items_run_field", table_name="research_extraction_items"); op.drop_table("research_extraction_items")
    op.drop_index("ix_research_extraction_runs_version_created", table_name="research_extraction_runs"); op.drop_table("research_extraction_runs")
