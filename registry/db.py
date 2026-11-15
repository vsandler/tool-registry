"""SQLite database: opening a connection and creating the tables."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    role       TEXT NOT NULL CHECK (role IN (
                   'builder', 'practice_admin', 'super_admin',
                   'specialist_reviewer', 'tool_user')),
    practice   TEXT,
    specialty  TEXT CHECK (specialty IS NULL OR specialty IN (
                   'compliance', 'marketing', 'technology')),
    active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tools (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    template    TEXT NOT NULL,
    variables   TEXT NOT NULL DEFAULT '[]',   -- JSON list of declared variable names
    visibility  TEXT NOT NULL CHECK (visibility IN ('practice-only', 'firm-wide')),
    practice    TEXT,
    owner_id    TEXT NOT NULL REFERENCES users(id),
    rationale   TEXT NOT NULL DEFAULT '',     -- why it was built this way
    status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                    'draft', 'in_review', 'approved', 'rejected')),
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS check_results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id    INTEGER NOT NULL REFERENCES tools(id),
    check_name TEXT NOT NULL,
    passed     INTEGER NOT NULL,
    message    TEXT NOT NULL,
    checked_at TEXT NOT NULL
);

-- The approval order, stored as an ordered list of steps (DECISIONS.md #1).
CREATE TABLE IF NOT EXISTS approval_steps (
    position      INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    approver_role TEXT NOT NULL
);

-- Approval history: one row per decision, never edited or deleted.
CREATE TABLE IF NOT EXISTS approvals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id     INTEGER NOT NULL REFERENCES tools(id),
    position    INTEGER NOT NULL,
    step_name   TEXT NOT NULL,
    approver_id TEXT NOT NULL REFERENCES users(id),
    decision    TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    comment     TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL
);
"""


def connect(path: str = "registry.db") -> sqlite3.Connection:
    """Open the database. Use ":memory:" for a throwaway database (tests)."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
