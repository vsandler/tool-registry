"""The approval flow.

The order is stored as an ordered list of steps in the `approval_steps` table
(DECISIONS.md #1), so a configurable order (BACKLOG.md) can replace it later
without a rewrite. Each step says which role approves it.

Rules:
  1. Steps happen strictly in order.
  2. Only the role named on the current step can decide it.
  3. Nobody can approve or reject their own tool, admins included.
  4. One person can decide at most one step of the same tool, so each step
     gets a different pair of eyes.
  5. Every decision is recorded in the history and never changed.
  6. A rejection ends the review; approving the last step approves the tool.
"""

import sqlite3

from registry.personas import ROLES, get_user
from registry.tools import ToolError, get_tool, now


class ApprovalError(ToolError):
    """Raised when an approval decision isn't allowed."""


DECISIONS = ("approved", "rejected")


def set_steps(conn: sqlite3.Connection, steps: list[dict]) -> None:
    """Replace the approval order. `steps` is an ordered list of
    {"name": ..., "approver_role": ...}."""
    if not steps:
        raise ApprovalError("The approval order needs at least one step")
    for step in steps:
        if step["approver_role"] not in ROLES:
            raise ApprovalError(f"Unknown role {step['approver_role']!r}")
    conn.execute("DELETE FROM approval_steps")
    conn.executemany(
        "INSERT INTO approval_steps (position, name, approver_role) VALUES (?, ?, ?)",
        [(i, s["name"], s["approver_role"]) for i, s in enumerate(steps, start=1)],
    )
    conn.commit()


def get_steps(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT position, name, approver_role FROM approval_steps ORDER BY position")
    return [dict(r) for r in rows]


def get_history(conn: sqlite3.Connection, tool_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT a.position, a.step_name, a.approver_id, u.name AS approver_name, u.role AS "
        "approver_role, a.decision, a.comment, a.decided_at "
        "FROM approvals a JOIN users u ON u.id = a.approver_id "
        "WHERE a.tool_id = ? ORDER BY a.id",
        (tool_id,),
    )
    return [dict(r) for r in rows]


def current_step(conn: sqlite3.Connection, tool_id: int) -> dict | None:
    """The next step waiting for a decision, or None if the review is over."""
    tool = get_tool(conn, tool_id)
    if tool is None or tool["status"] != "in_review":
        return None
    done = {h["position"] for h in get_history(conn, tool_id) if h["decision"] == "approved"}
    for step in get_steps(conn):
        if step["position"] not in done:
            return step
    return None


def decide(
    conn: sqlite3.Connection, tool_id: int, user_id: str, decision: str, comment: str = ""
) -> dict:
    """Record one approver's decision on the tool's current step. Returns the updated tool."""
    if decision not in DECISIONS:
        raise ApprovalError(f"Decision must be one of {DECISIONS}")
    tool = get_tool(conn, tool_id)
    if tool is None:
        raise ApprovalError(f"Tool {tool_id} not found")
    user = get_user(conn, user_id)
    if user is None:
        raise ApprovalError(f"User {user_id} not found")

    # Rule 3 comes first so the reason is clear, whatever the person's role.
    if tool["owner_id"] == user_id:
        raise ApprovalError("You can't approve or reject your own tool, even as an admin")
    if tool["status"] != "in_review":
        raise ApprovalError(f"This tool isn't in review (it is {tool['status']})")
    if not get_steps(conn):
        raise ApprovalError("No approval order has been set up")

    step = current_step(conn, tool_id)
    if user["role"] != step["approver_role"]:
        raise ApprovalError(
            f"Step {step['position']} ({step['name']}) must be decided by a "
            f"{step['approver_role']}, not a {user['role']}"
        )
    if any(h["approver_id"] == user_id for h in get_history(conn, tool_id)):
        raise ApprovalError("You've already decided a step of this tool; another person must "
                            "decide this one")

    conn.execute(
        "INSERT INTO approvals (tool_id, position, step_name, approver_id, decision, comment, "
        "decided_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tool_id, step["position"], step["name"], user_id, decision, comment, now()),
    )
    if decision == "rejected":
        conn.execute("UPDATE tools SET status = 'rejected' WHERE id = ?", (tool_id,))
    elif current_step(conn, tool_id) is None:
        conn.execute("UPDATE tools SET status = 'approved' WHERE id = ?", (tool_id,))
    conn.commit()
    return get_tool(conn, tool_id)
