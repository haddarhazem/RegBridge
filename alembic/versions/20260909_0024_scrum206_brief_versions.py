"""Add immutable review versions and exact-version verification links."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "scrum206_brief_versions"
down_revision = "scrum205_brief_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)

    op.drop_constraint("ck_investor_opportunity_brief_status", "investor_opportunity_brief_runs", type_="check")
    op.create_check_constraint(
        "ck_investor_opportunity_brief_status",
        "investor_opportunity_brief_runs",
        "status IN ('DRAFT', 'UNVERIFIED', 'VERIFIED', 'VERIFICATION_FAILED', 'APPROVED')",
    )

    op.create_table(
        "investor_opportunity_brief_versions",
        sa.Column("id", u, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("brief_run_id", u, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("author_user_id", u, nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(30), server_default="DRAFT", nullable=False),
        sa.Column("investor_thesis_version_id", u, nullable=False),
        sa.Column("startup_snapshot_revision_id", u, nullable=True),
        sa.Column("matching_run_id", u, nullable=True),
        sa.Column("generation_strategy", sa.String(60), nullable=False),
        sa.Column("generation_version", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("model", sa.String(120)),
        sa.Column("prompt_version", sa.String(80)),
        sa.Column("approved_by_user_id", u, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_investor_opportunity_brief_versions"),
        sa.ForeignKeyConstraint(["brief_run_id"], ["investor_opportunity_brief_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["investor_thesis_version_id"], ["investor_thesis_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["startup_snapshot_revision_id"], ["startup_profile_revisions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["matching_run_id"], ["investment_matching_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("brief_run_id", "version_number", name="uq_brief_version_number"),
        sa.CheckConstraint("version_number > 0", name="ck_brief_version_number_positive"),
        sa.CheckConstraint("status IN ('DRAFT', 'UNVERIFIED', 'VERIFIED', 'VERIFICATION_FAILED', 'APPROVED')", name="ck_brief_version_status"),
    )
    op.create_index("ix_brief_versions_brief_number", "investor_opportunity_brief_versions", ["brief_run_id", "version_number"])

    op.execute(sa.text("""
        INSERT INTO investor_opportunity_brief_versions (
            brief_run_id, version_number, author_user_id, content, status,
            investor_thesis_version_id, startup_snapshot_revision_id, matching_run_id,
            generation_strategy, generation_version, provider, model, prompt_version, created_at
        )
        SELECT id, 1, investor_user_id, content, status,
               investor_thesis_version_id, startup_snapshot_revision_id, matching_run_id,
               generation_strategy, generation_version, provider, model, prompt_version, created_at
        FROM investor_opportunity_brief_runs
    """))

    op.add_column(
        "investor_opportunity_brief_verification_runs",
        sa.Column("brief_version_id", u, nullable=True),
    )
    op.create_foreign_key(
        "fk_brief_verification_runs_version",
        "investor_opportunity_brief_verification_runs",
        "investor_opportunity_brief_versions",
        ["brief_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(sa.text("""
        UPDATE investor_opportunity_brief_verification_runs AS verification
        SET brief_version_id = version.id
        FROM investor_opportunity_brief_versions AS version
        WHERE version.brief_run_id = verification.brief_run_id
          AND version.version_number = 1
    """))


def downgrade() -> None:
    op.drop_constraint("fk_brief_verification_runs_version", "investor_opportunity_brief_verification_runs", type_="foreignkey")
    op.drop_column("investor_opportunity_brief_verification_runs", "brief_version_id")
    op.drop_index("ix_brief_versions_brief_number", table_name="investor_opportunity_brief_versions")
    op.drop_table("investor_opportunity_brief_versions")
    op.drop_constraint("ck_investor_opportunity_brief_status", "investor_opportunity_brief_runs", type_="check")
    op.create_check_constraint(
        "ck_investor_opportunity_brief_status",
        "investor_opportunity_brief_runs",
        "status IN ('DRAFT', 'UNVERIFIED', 'VERIFIED', 'VERIFICATION_FAILED')",
    )
