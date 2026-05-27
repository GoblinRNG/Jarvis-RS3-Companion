"""SQLite schema initialisation for the RS3 JARVIS knowledge database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH_DEFAULT = Path.home() / ".jarvis_rs3" / "rs3.db"

_DDL = """
CREATE TABLE IF NOT EXISTS training_methods (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    skill            TEXT    NOT NULL,
    method_name      TEXT    NOT NULL,
    lo_lvl           INTEGER NOT NULL DEFAULT 1,
    hi_lvl           INTEGER NOT NULL DEFAULT 120,
    xp_per_hr        INTEGER NOT NULL DEFAULT 0,
    gp_cost_per_hr   INTEGER NOT NULL DEFAULT 0,  -- negative = profit
    intensity        TEXT    NOT NULL DEFAULT 'semi',  -- afk|semi|intensive
    requirements_json TEXT   DEFAULT '{}',
    notes            TEXT    DEFAULT '',
    last_verified    TEXT    DEFAULT (date('now')),
    UNIQUE(skill, method_name)
);

CREATE TABLE IF NOT EXISTS money_making (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    method           TEXT    NOT NULL UNIQUE,
    gp_per_hr        INTEGER NOT NULL DEFAULT 0,
    requirements_json TEXT   DEFAULT '{}',
    intensity        TEXT    NOT NULL DEFAULT 'semi',
    is_boss          INTEGER NOT NULL DEFAULT 0,
    notes            TEXT    DEFAULT '',
    last_verified    TEXT    DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS quests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL UNIQUE,
    qp               INTEGER NOT NULL DEFAULT 1,
    qp_required      INTEGER NOT NULL DEFAULT 0,
    skill_reqs_json  TEXT    DEFAULT '{}',
    quest_reqs_json  TEXT    DEFAULT '[]',
    rewards_json     TEXT    DEFAULT '{}',
    difficulty       TEXT    DEFAULT 'novice',
    length           TEXT    DEFAULT 'short',
    series           TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bosses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL UNIQUE,
    hp               INTEGER NOT NULL DEFAULT 0,
    weakness         TEXT    DEFAULT '',
    kill_time_p50    INTEGER NOT NULL DEFAULT 60,  -- seconds
    kill_time_p10    INTEGER NOT NULL DEFAULT 30,
    drop_table_json  TEXT    DEFAULT '{}',
    gp_per_hr_p50    INTEGER NOT NULL DEFAULT 0,
    gp_per_hr_p10    INTEGER NOT NULL DEFAULT 0,
    notes            TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS teleports (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    region           TEXT    NOT NULL DEFAULT '',
    x                INTEGER DEFAULT 0,
    y                INTEGER DEFAULT 0,
    item_required    TEXT    DEFAULT '',
    cooldown_s       INTEGER DEFAULT 0,
    type             TEXT    DEFAULT 'lodestone'
);

CREATE TABLE IF NOT EXISTS dailies (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL UNIQUE,
    reset_type       TEXT    NOT NULL DEFAULT 'daily',  -- daily|weekly|monthly
    category         TEXT    DEFAULT '',
    gp_value         INTEGER DEFAULT 0,
    xp_value         INTEGER DEFAULT 0,
    notes            TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS player_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_training_skill      ON training_methods(skill, lo_lvl, hi_lvl);
CREATE INDEX IF NOT EXISTS idx_money_intensity     ON money_making(intensity, gp_per_hr);
CREATE INDEX IF NOT EXISTS idx_quests_name         ON quests(name);
CREATE INDEX IF NOT EXISTS idx_bosses_name         ON bosses(name);
"""


def init_db(db_path: Path | None = None) -> Path:
    """Create the database and all tables if they do not already exist.

    Parameters
    ----------
    db_path:
        Override the default path (~/.jarvis_rs3/rs3.db).

    Returns
    -------
    The resolved path to the database file.
    """
    path = (db_path or DB_PATH_DEFAULT).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_DDL)
        conn.commit()
    finally:
        conn.close()

    return path
