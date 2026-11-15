"""Tools: reusable templates with {{variables}} and a visibility label."""

import json
import re
import sqlite3
from datetime import datetime, timezone

VISIBILITIES = ("practice-only", "firm-wide")

# A template variable looks like {{client_name}}: letters, digits, underscores.
VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class ToolError(ValueError):
    """Raised when a tool request can't be carried out."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def find_variables(template: str) -> list[str]:
    """Variable names used in a template, in first-seen order, no repeats."""
    seen: list[str] = []
    for name in VARIABLE_PATTERN.findall(template):
        if name not in seen:
            seen.append(name)
    return seen


def render(template: str, values: dict[str, str]) -> str:
    """Fill in a template for one user's personal copy. Every variable needs a value."""
    missing = [v for v in find_variables(template) if v not in values]
    if missing:
        raise ToolError(f"Missing values for: {', '.join(missing)}")
    return VARIABLE_PATTERN.sub(lambda m: str(values[m.group(1)]), template)


def create_tool(
    conn: sqlite3.Connection,
    *,
    name: str,
    template: str,
    owner_id: str,
    visibility: str,
    variables: list[str] | None = None,
    description: str = "",
    practice: str | None = None,
    rationale: str = "",
) -> int:
    """Save a new tool as a draft and return its id.

    If `variables` is not given, the variables found in the template are used.
    """
    if visibility not in VISIBILITIES:
        raise ToolError(f"Visibility must be one of {VISIBILITIES}, not {visibility!r}")
    if variables is None:
        variables = find_variables(template)
    cur = conn.execute(
        "INSERT INTO tools (name, description, template, variables, visibility, practice, "
        "owner_id, rationale, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
        (name, description, template, json.dumps(variables), visibility, practice,
         owner_id, rationale, now()),
    )
    conn.commit()
    return cur.lastrowid


def get_tool(conn: sqlite3.Connection, tool_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
    if row is None:
        return None
    tool = dict(row)
    tool["variables"] = json.loads(tool["variables"])
    return tool


def list_tools(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = conn.execute("SELECT id FROM tools WHERE status = ? ORDER BY id", (status,))
    else:
        rows = conn.execute("SELECT id FROM tools ORDER BY id")
    return [get_tool(conn, r["id"]) for r in rows.fetchall()]
