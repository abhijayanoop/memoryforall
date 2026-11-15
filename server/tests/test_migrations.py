import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

DATABASE_URL = os.environ.get("DATABASE_URL")

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="needs DATABASE_URL (Postgres)")


def test_upgrade_head_creates_spec1_tables() -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(str(DATABASE_URL))).get_table_names())
    assert {"devices", "raw_payloads", "conversations", "messages"} <= tables
