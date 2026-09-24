"""Match the V2.1 contract-analysis version foreign key.

Revision ID: contract_analysis_v21_fk
Revises: contract_agent_analyzer
"""

from alembic import op


revision = "contract_analysis_v21_fk"
down_revision = "contract_agent_analyzer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_contract_analyses_document_version_id_document_versions",
        "contract_analyses",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_contract_analyses_document_version_id_document_versions",
        "contract_analyses",
        "document_versions",
        ["document_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_contract_analyses_document_version_id_document_versions",
        "contract_analyses",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_contract_analyses_document_version_id_document_versions",
        "contract_analyses",
        "document_versions",
        ["document_version_id"],
        ["id"],
        ondelete="CASCADE",
    )
