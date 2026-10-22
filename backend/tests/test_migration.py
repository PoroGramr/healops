import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa


def test_fresh_database_migrates_to_head(tmp_path):
    db = tmp_path / "healops.db"
    env = {**os.environ, "HEALOPS_DB_URL": f"sqlite:///{db}"}
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    with sa.create_engine(f"sqlite:///{db}").connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0002"
        columns = {c["name"] for c in sa.inspect(conn).get_columns("containers")}
        assert "failure_streak" in columns
