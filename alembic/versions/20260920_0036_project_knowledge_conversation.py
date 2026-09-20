"""Allow generic provider facts for conversational project knowledge.

Revision ID: project_knowledge_conversation
Revises: launch_roadmap_semantics
"""

from alembic import op


revision = "project_knowledge_conversation"
down_revision = "launch_roadmap_semantics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_project_facts_domain", "project_facts", type_="check")
    op.create_check_constraint(
        "ck_project_facts_domain",
        "project_facts",
        "domain IN ('activity', 'sector', 'technology', 'data', 'market', 'location', 'provider')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_project_facts_domain", "project_facts", type_="check")
    op.create_check_constraint(
        "ck_project_facts_domain",
        "project_facts",
        "domain IN ('activity', 'sector', 'technology', 'data', 'market', 'location')",
    )
