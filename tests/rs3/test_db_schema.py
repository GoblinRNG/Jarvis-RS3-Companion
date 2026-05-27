"""Tests for RS3 database schema initialisation and seed data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from openjarvis.rs3.db.schema import init_db
from openjarvis.rs3.db.seed_data import seed_all


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = init_db(tmp_path / "test_rs3.db")
    seed_all(path)
    return path


class TestSchemaInit:
    def test_creates_file(self, tmp_path: Path):
        p = init_db(tmp_path / "rs3.db")
        assert p.exists()

    def test_idempotent(self, tmp_path: Path):
        p = tmp_path / "rs3.db"
        init_db(p)
        init_db(p)  # second call must not raise
        assert p.exists()

    def test_all_tables_exist(self, db: Path):
        conn = sqlite3.connect(str(db))
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        expected = {
            "training_methods", "money_making", "quests",
            "bosses", "teleports", "dailies", "player_state",
        }
        assert expected.issubset(tables)


class TestSeedData:
    def test_training_methods_seeded(self, db: Path):
        conn = sqlite3.connect(str(db))
        count = conn.execute("SELECT COUNT(*) FROM training_methods").fetchone()[0]
        conn.close()
        assert count > 10

    def test_money_making_seeded(self, db: Path):
        conn = sqlite3.connect(str(db))
        count = conn.execute("SELECT COUNT(*) FROM money_making").fetchone()[0]
        conn.close()
        assert count > 5

    def test_quests_seeded(self, db: Path):
        conn = sqlite3.connect(str(db))
        count = conn.execute("SELECT COUNT(*) FROM quests").fetchone()[0]
        conn.close()
        assert count > 5

    def test_bosses_seeded(self, db: Path):
        conn = sqlite3.connect(str(db))
        count = conn.execute("SELECT COUNT(*) FROM bosses").fetchone()[0]
        conn.close()
        assert count > 3

    def test_teleports_seeded(self, db: Path):
        conn = sqlite3.connect(str(db))
        count = conn.execute("SELECT COUNT(*) FROM teleports").fetchone()[0]
        conn.close()
        assert count > 5

    def test_dailies_seeded(self, db: Path):
        conn = sqlite3.connect(str(db))
        count = conn.execute("SELECT COUNT(*) FROM dailies").fetchone()[0]
        conn.close()
        assert count > 5

    def test_seed_idempotent(self, db: Path):
        # Running seed_all twice must not duplicate rows
        seed_all(db)
        conn = sqlite3.connect(str(db))
        c1 = conn.execute("SELECT COUNT(*) FROM training_methods").fetchone()[0]
        conn.close()
        seed_all(db)
        conn = sqlite3.connect(str(db))
        c2 = conn.execute("SELECT COUNT(*) FROM training_methods").fetchone()[0]
        conn.close()
        assert c1 == c2

    def test_slayer_methods_present(self, db: Path):
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT method_name FROM training_methods WHERE skill='slayer'"
        ).fetchall()
        conn.close()
        assert len(rows) > 0

    def test_telos_in_bosses(self, db: Path):
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT * FROM bosses WHERE name LIKE '%Telos%'"
        ).fetchone()
        conn.close()
        assert row is not None
