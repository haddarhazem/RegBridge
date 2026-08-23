"""Add investor profiles and immutable thesis versions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "scrum198_investor_thesis"
down_revision = "scrum197_grant_uniqueness"
branch_labels = None
depends_on = None

def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table("investor_profiles",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("current_version_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_investor_profiles"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_investor_profiles_user"),
    )
    op.create_table("investor_thesis_versions",
        sa.Column("id", uuid_type, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("investor_profile_id", uuid_type, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("sectors", postgresql.JSONB(), nullable=True),
        sa.Column("stages", postgresql.JSONB(), nullable=True),
        sa.Column("geographies", postgresql.JSONB(), nullable=True),
        sa.Column("technologies", postgresql.JSONB(), nullable=True),
        sa.Column("ticket_min", sa.Numeric(18, 2), nullable=True),
        sa.Column("ticket_max", sa.Numeric(18, 2), nullable=True),
        sa.Column("ticket_currency", sa.String(3), nullable=True),
        sa.Column("source", sa.String(30), server_default="USER_DECLARED", nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_investor_thesis_versions"),
        sa.ForeignKeyConstraint(["investor_profile_id"], ["investor_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("investor_profile_id", "version_number", name="uq_investor_thesis_versions_number"),
        sa.CheckConstraint("ticket_min IS NULL OR ticket_min >= 0", name="investor_thesis_ticket_min_nonnegative"),
        sa.CheckConstraint("ticket_max IS NULL OR ticket_max >= 0", name="investor_thesis_ticket_max_nonnegative"),
        sa.CheckConstraint("ticket_min IS NULL OR ticket_max IS NULL OR ticket_min <= ticket_max", name="investor_thesis_ticket_range"),
    )
    op.create_foreign_key("fk_investor_profiles_current_version", "investor_profiles", "investor_thesis_versions", ["current_version_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_investor_thesis_versions_profile_created", "investor_thesis_versions", ["investor_profile_id", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_investor_thesis_versions_profile_created", table_name="investor_thesis_versions")
    op.drop_constraint("fk_investor_profiles_current_version", "investor_profiles", type_="foreignkey")
    op.drop_table("investor_thesis_versions")
    op.drop_table("investor_profiles")
