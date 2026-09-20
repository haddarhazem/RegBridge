"""Keep deleted project facts as non-active lifecycle history.

Revision ID: project_fact_deleted_history
Revises: project_knowledge_conversation
"""

from alembic import op
import sqlalchemy as sa


revision = "project_fact_deleted_history"
down_revision = "project_knowledge_conversation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The original constraint included ``status`` but still prevented the
    # confirmed fact and its confirmed removal proposal from both becoming
    # deleted. Deleted records are audit history, so exclude them while
    # retaining the established active-value uniqueness semantics.
    op.drop_constraint("uq_project_facts_active_value", "project_facts", type_="unique")
    op.create_index(
        "uq_project_facts_active_value",
        "project_facts",
        ["project_id", "domain", "value", "status"],
        unique=True,
        postgresql_where=sa.text("status <> 'deleted'"),
    )


def downgrade() -> None:
    op.drop_index("uq_project_facts_active_value", table_name="project_facts")
    op.create_unique_constraint(
        "uq_project_facts_active_value",
        "project_facts",
        ["project_id", "domain", "value", "status"],
    )
