"""Tools: reusable templates with {{variables}} and a visibility label."""

import json
import re
import sqlite3
from datetime import datetime, timezone

VISIBILITIES = ("practice-only", "firm-wide")

# A template variable looks like {{client_name}}: letters, digits, underscores.
VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class ToolError(ValueError):
    """Raised when a tool request can't be carried out (bad input)."""


class NotFound(ToolError):
    """The tool or user doesn't exist."""


class NotAllowed(ToolError):
    """The person isn't allowed to do this."""


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


def submit_tool(conn: sqlite3.Connection, tool_id: int, user_id: str, *,
                sample_advice=None) -> dict:
    """Send a draft for review. The rule-based checks and the AI pre-review both run,
    and their results are saved.

    Flagged tools still go into review: a human decides. Nothing is auto-rejected.
    The AI's verdict is advice only: it doesn't change the status or the approval
    steps, and if the AI call fails the tool is still submitted (marked needs_human).
    Returns {"tool": ..., "checks": [...], "flagged": bool, "ai_review": {...}}.
    `flagged` is the rule-based checks only; the AI's own flag is in `ai_review`.

    `sample_advice` (a ReviewResult) is used only by the seed data: it stores that
    pre-written advice, labelled as sample advice, instead of calling the AI.
    Real submissions never pass it, so they always call the AI.
    """
    # Imported here to avoid circular imports (both modules import from this one).
    from registry import agent
    from registry.checks import run_checks, save_check_results

    tool = get_tool(conn, tool_id)
    if tool is None:
        raise NotFound(f"Tool {tool_id} not found")
    if tool["owner_id"] != user_id:
        raise NotAllowed("Only the tool's owner can submit it")
    if tool["status"] != "draft":
        raise NotAllowed(f"Only drafts can be submitted; this tool is {tool['status']}")
    results = run_checks(conn, tool)
    if sample_advice is None:
        ai_result = agent.review_for_submission(tool)  # never raises
    else:
        ai_result = sample_advice
    save_check_results(conn, tool_id, results)
    agent.save_ai_review(conn, tool_id, ai_result, is_sample=sample_advice is not None)
    conn.execute("UPDATE tools SET status = 'in_review' WHERE id = ?", (tool_id,))
    conn.commit()
    return {
        "tool": get_tool(conn, tool_id),
        "checks": [r.__dict__ for r in results],
        "flagged": any(not r.passed for r in results),
        "ai_review": agent.get_ai_review(conn, tool_id),
    }


def list_tools(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = conn.execute("SELECT id FROM tools WHERE status = ? ORDER BY id", (status,))
    else:
        rows = conn.execute("SELECT id FROM tools ORDER BY id")
    return [get_tool(conn, r["id"]) for r in rows.fetchall()]
