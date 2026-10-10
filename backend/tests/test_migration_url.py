import runpy
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from alembic.config import Config
from sqlalchemy.engine import URL, make_url


@pytest.mark.parametrize("password", ["synthetic-password", "synthetic@pass:%/word"])
@pytest.mark.parametrize("offline", [False, True])
def test_migration_environment_preserves_database_password(password, offline):
    url = URL.create(
        "postgresql+psycopg",
        username="test_user",
        password=password,
        host="localhost",
        database="test_database",
    )
    config = Config()
    migration_engine = Mock(url=url)
    connectable = Mock()
    connectable.connect.return_value.__enter__ = Mock()
    connectable.connect.return_value.__exit__ = Mock(return_value=False)

    with (
        patch("alembic.context.config", config, create=True),
        patch("alembic.context.is_offline_mode", return_value=offline),
        patch("alembic.context.configure") as configure,
        patch("alembic.context.begin_transaction"),
        patch("alembic.context.run_migrations"),
        patch("app.database.engine", migration_engine),
        patch("sqlalchemy.engine_from_config", return_value=connectable) as factory,
    ):
        runpy.run_path(str(Path(__file__).parents[1] / "alembic" / "env.py"))

    if offline:
        configured_url = configure.call_args.kwargs["url"]
    else:
        configured_url = factory.call_args.args[0]["sqlalchemy.url"]
    assert make_url(configured_url).password == password
