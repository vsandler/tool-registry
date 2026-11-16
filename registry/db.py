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
                    'draft', 'in_review', 'published', 'rejected')),
    routed_to   TEXT CHECK (routed_to IS NULL OR routed_to IN (
                    'compliance', 'marketing', 'technology')),
    created_at  TEXT NOT NULL,
    submitted_at TEXT                         -- set when the owner submits it for review
);

CREATE TABLE IF NOT EXISTS check_results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id    INTEGER NOT NULL REFERENCES tools(id),
    check_name TEXT NOT NULL,
    passed     INTEGER NOT NULL,
    message    TEXT NOT NULL,
    checked_at TEXT NOT NULL
);

-- AI pre-review advice, one row per submission. Advice only: it never approves
-- or rejects. verdict 'needs_human' means the AI call or its reply failed.
CREATE TABLE IF NOT EXISTS ai_reviews (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id          INTEGER NOT NULL REFERENCES tools(id),
    verdict          TEXT NOT NULL CHECK (verdict IN ('risky', 'safe', 'needs_human')),
    issues           TEXT NOT NULL DEFAULT '[]',  -- JSON list of short issue strings
    reason           TEXT NOT NULL DEFAULT '',
    model            TEXT NOT NULL,
    input_tokens     INTEGER NOT NULL DEFAULT 0,
    output_tokens    INTEGER NOT NULL DEFAULT 0,
    cost_usd         REAL,
    response_seconds REAL NOT NULL DEFAULT 0,
    error            TEXT,
    is_sample        INTEGER NOT NULL DEFAULT 0,  -- 1 = pre-written demo advice, not a live call
    reviewed_at      TEXT NOT NULL
);

-- The approval order, stored as an ordered list of steps (DECISIONS.md #1).
CREATE TABLE IF NOT EXISTS approval_steps (
    position         INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    approver_role    TEXT NOT NULL,
    action           TEXT NOT NULL CHECK (action IN ('route', 'review', 'publish')),
    different_person INTEGER NOT NULL DEFAULT 0  -- 1 = must be someone who decided no other step
);

-- Each routed tool's own list of approval steps (DECISIONS.md #11), made when the
-- Super admin routes it: route -> one review per chosen area, in order -> publish.
-- Tools with no rows here (not yet routed, or routed before #11) use approval_steps.
CREATE TABLE IF NOT EXISTS tool_steps (
    tool_id          INTEGER NOT NULL REFERENCES tools(id),
    position         INTEGER NOT NULL,
    name             TEXT NOT NULL,
    approver_role    TEXT NOT NULL,
    action           TEXT NOT NULL CHECK (action IN ('route', 'review', 'publish')),
    area             TEXT CHECK (area IS NULL OR area IN (
                         'compliance', 'marketing', 'technology')),
    different_person INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tool_id, position)
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
    detail      TEXT NOT NULL DEFAULT '',     -- e.g. "routed to compliance"
    decided_at  TEXT NOT NULL
);
"""


def connect(path: str = "registry.db") -> sqlite3.Connection:
    """Open the database. Use ":memory:" for a throwaway database (tests)."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _add_missing_columns(conn)
    return conn


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Upgrade a database made by an older version of this code.

    CREATE TABLE IF NOT EXISTS doesn't add new columns to a table that already
    exists, so add them here. Safe to run every time.
    """
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(ai_reviews)")}
    if "is_sample" not in columns:
        conn.execute("ALTER TABLE ai_reviews ADD COLUMN is_sample INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    columns = {r["name"] for r in conn.execute("PRAGMA table_info(tools)")}
    if "submitted_at" not in columns:
        conn.execute("ALTER TABLE tools ADD COLUMN submitted_at TEXT")
        # Tools submitted before this column existed: use when their checks first ran,
        # which happens at submission. Drafts stay empty.
        conn.execute(
            "UPDATE tools SET submitted_at = (SELECT MIN(checked_at) FROM check_results "
            "WHERE check_results.tool_id = tools.id) WHERE status != 'draft'")
        conn.commit()
