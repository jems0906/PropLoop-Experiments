import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


def test_upgrade_preserves_existing_experiment(tmp_path):
    backend = Path(__file__).parents[1]
    database = tmp_path / "migration.db"
    url = "sqlite:///" + str(database)
    environment = {**os.environ, "DATABASE_URL": url}

    def migrate(target):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", target],
            cwd=backend, env=environment, text=True, capture_output=True, timeout=60,
        )
        assert result.returncode == 0, result.stderr

    migrate("0003_controlled_tests")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO experiments (id, name, hypothesis, problem_statement, target_metric, stage, spec_approved, plan_approved, created_at, updated_at) "
            "VALUES (7, 'Existing pilot', 'Existing hypothesis', 'Existing problem', 'Activation', 'hypothesis', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    migrate("head")
    with engine.connect() as connection:
        row = connection.execute(text("SELECT name, cycle, approvals, history FROM experiments WHERE id = 7")).one()
        assert tuple(row) == ("Existing pilot", 1, "[]", "[]")
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0005_lifecycle_outcomes"
    assert "observations" in inspect(engine).get_table_names()
    engine.dispose()
