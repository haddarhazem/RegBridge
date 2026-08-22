import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://regbridge:regbridge@127.0.0.1:55432/regbridge")

import app.db.models  # noqa: F401 - register the complete ORM metadata for every test order
