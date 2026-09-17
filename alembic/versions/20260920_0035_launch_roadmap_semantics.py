"""Allow project-first startup launch roadmaps with optional enrichment."""

from alembic import op
import sqlalchemy as sa


revision = "launch_roadmap_semantics"
down_revision = "runtime_context_bounds"
branch_labels = None
depends_on = None


_ITEM_TYPES = (
    "'obligation', 'recommendation', 'uncertainty', "
    "'administrative', 'legal', 'finance', 'contracts', 'privacy', "
    "'security', 'regulatory', 'ip', 'hr', 'launch'"
)


def upgrade() -> None:
    op.alter_column(
        "launch_roadmaps",
        "regulatory_assessment_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.drop_constraint("launch_roadmap_items_type", "launch_roadmap_items", type_="check")
    op.create_check_constraint(
        "launch_roadmap_items_type",
        "launch_roadmap_items",
        f"item_type IN ({_ITEM_TYPES})",
    )


def downgrade() -> None:
    # Baseline-only versions cannot satisfy the historical mandatory FK.
    op.execute("DELETE FROM launch_roadmaps WHERE regulatory_assessment_id IS NULL")
    op.drop_constraint("launch_roadmap_items_type", "launch_roadmap_items", type_="check")
    op.create_check_constraint(
        "launch_roadmap_items_type",
        "launch_roadmap_items",
        "item_type IN ('obligation', 'recommendation', 'uncertainty')",
    )
    op.alter_column(
        "launch_roadmaps",
        "regulatory_assessment_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
