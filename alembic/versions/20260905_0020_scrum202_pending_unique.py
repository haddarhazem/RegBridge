"""Make pending contact request uniqueness NULL-safe."""
from alembic import op
import sqlalchemy as sa

revision = "scrum202_pending_unique"
down_revision = "scrum202_contact_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ux_contact_requests_pending", table_name="contact_requests")
    op.create_index(
        "ux_contact_requests_pending",
        "contact_requests",
        ["requester_user_id", "target_type", "target_id", sa.text("coalesce(source_project_id, '00000000-0000-0000-0000-000000000000'::uuid)")],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ux_contact_requests_pending", table_name="contact_requests")
    op.create_index(
        "ux_contact_requests_pending",
        "contact_requests",
        ["requester_user_id", "target_type", "target_id", "source_project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
