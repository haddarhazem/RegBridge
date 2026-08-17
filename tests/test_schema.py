from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base
import app.db.models  # noqa: F401


EXPECTED_TABLES = {
    "users",
    "user_identities",
    "roles",
    "user_roles",
    "projects",
    "project_members",
    "audit_logs",
}


def test_single_metadata_contains_only_scrum177_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert "user_consents" not in Base.metadata.tables
    assert "project_access_grants" not in Base.metadata.tables
    assert "investor_profiles" not in Base.metadata.tables


def test_alembic_has_scrum177_head() -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()

    assert heads == ["scrum177_foundation"]
    assert script.get_revision("scrum177_foundation").down_revision is None
