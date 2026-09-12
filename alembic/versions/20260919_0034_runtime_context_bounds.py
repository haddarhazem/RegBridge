"""Allow the full bounded SCRUM-187 data context to reach the Copilot safely."""

from alembic import op
import sqlalchemy as sa


revision = "runtime_context_bounds"
down_revision = "self_service_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "projects",
        "data_context",
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "projects",
        "data_context",
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True,
    )
