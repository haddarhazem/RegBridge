"""Seed the provider-neutral global role catalog for self-service auth."""

from alembic import op


revision = "self_service_auth"
down_revision = "scrum212_grant_reissue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO roles (code, description)
        VALUES
          ('entrepreneur', 'Create or manage entrepreneurial projects'),
          ('investor', 'Discover authorized startup opportunities and manage an investment thesis'),
          ('researcher', 'Deposit research outputs and collaborate'),
          ('research_center', 'Manage research-center activities'),
          ('admin', 'Perform explicitly authorized platform administration')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM roles AS role
        WHERE role.code IN ('entrepreneur', 'investor', 'researcher', 'research_center', 'admin')
          AND NOT EXISTS (
            SELECT 1 FROM user_roles AS assignment WHERE assignment.role_id = role.id
          )
        """
    )
