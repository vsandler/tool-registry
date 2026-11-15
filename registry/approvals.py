"""The approval flow (DECISIONS.md #1).

The order is stored as an ordered list of steps in the `approval_steps` table,
so a configurable order (BACKLOG.md) can replace it later without a rewrite.
Each step names the role that decides it and what deciding it does:

  1. route   - Super admin approves and sends it to one specialist area
  2. review  - a Specialist reviewer from that area approves
  3. publish - back to the Super admin, who sets visibility and publishes

Rules:
  - Steps happen strictly in order.
  - Only the role named on the current step can decide it; for the review step,
    only a specialist from the area the tool was routed to.
  - Nobody can approve or reject their own tool, admins included.
  - The same Super admin may decide steps 1 and 3, but a step marked
    `different_person` (the specialist review) must be decided by someone who
    decided no other step of this tool.
  - Every decision is recorded in the history and never changed.
  - A rejection at any step is final (for now); publishing ends the review.
"""

import sqlite3

from registry.personas import ROLES, SPECIALIST_AREAS, get_user
from registry.tools import VISIBILITIES, ToolError, get_tool, now


class ApprovalError(ToolError):
    """Raised when an approval decision isn't allowed."""


DECISIONS = ("approved", "rejected")
ACTIONS = ("route", "review", "publish")

DEFAULT_APPROVAL_STEPS = [
    {"name": "Super admin routes to a specialist", "approver_role": "super_admin",
     "action": "route", "different_person": False},
    {"name": "Specialist review", "approver_role": "specialist_reviewer",
     "action": "review", "different_person": True},
    {"name": "Super admin sets visibility and publishes", "approver_role": "super_admin",
     "action": "publish", "different_person": False},
]


def set_steps(conn: sqlite3.Connection, steps: list[dict]) -> None:
    """Replace the approval order with an ordered list of steps."""
    if not steps:
        raise ApprovalError("The approval order needs at least one step")
    for step in steps:
        if step["approver_role"] not in ROLES:
            raise ApprovalError(f"Unknown role {step['approver_role']!r}")
        if step["action"] not in ACTIONS:
            raise ApprovalError(f"Unknown action {step['action']!r}")
    conn.execute("DELETE FROM approval_steps")
    conn.executemany(
        "INSERT INTO approval_steps (position, name, approver_role, action, different_person) "
        "VALUES (?, ?, ?, ?, ?)",
        [(i, s["name"], s["approver_role"], s["action"], int(s.get("different_person", False)))
         for i, s in enumerate(steps, start=1)],
    )
    conn.commit()


def ensure_default_steps(conn: sqlite3.Connection) -> None:
    """Install the fixed default order if no order has been set up yet."""
    if not get_steps(conn):
        set_steps(conn, DEFAULT_APPROVAL_STEPS)


def get_steps(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT position, name, approver_role, action, different_person "
        "FROM approval_steps ORDER BY position")
    return [{**dict(r), "different_person": bool(r["different_person"])} for r in rows]


def get_history(conn: sqlite3.Connection, tool_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT a.position, a.step_name, a.approver_id, u.name AS approver_name, "
        "u.role AS approver_role, a.decision, a.comment, a.detail, a.decided_at "
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
    conn: sqlite3.Connection,
    tool_id: int,
    user_id: str,
    decision: str,
    comment: str = "",
    *,
    route_to: str | None = None,
    visibility: str | None = None,
    practice: str | None = None,
) -> dict:
    """Record one decision on the tool's current step. Returns the updated tool.

    - Approving a `route` step needs `route_to` (a specialist area).
    - Approving a `publish` step needs `visibility`; practice-only also needs a
      practice (given here, or already on the tool).
    """
    if decision not in DECISIONS:
        raise ApprovalError(f"Decision must be one of {DECISIONS}")
    tool = get_tool(conn, tool_id)
    if tool is None:
        raise ApprovalError(f"Tool {tool_id} not found")
    user = get_user(conn, user_id)
    if user is None:
        raise ApprovalError(f"User {user_id} not found")

    # No self-approval comes first, so the reason is clear whatever the role.
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
    if step["action"] == "review" and user["specialty"] != tool["routed_to"]:
        raise ApprovalError(
            f"This tool was routed to {tool['routed_to']}; a {user['specialty']} "
            "specialist can't decide it"
        )
    history = get_history(conn, tool_id)
    if step["different_person"] and any(h["approver_id"] == user_id for h in history):
        raise ApprovalError("This step must be decided by someone who hasn't decided another "
                            "step of this tool")

    detail = ""
    updates: dict = {}
    if decision == "approved" and step["action"] == "route":
        if route_to not in SPECIALIST_AREAS:
            raise ApprovalError(
                f"Choose a specialist area to route to: {', '.join(SPECIALIST_AREAS)}")
        updates["routed_to"] = route_to
        detail = f"routed to {route_to}"
    elif decision == "approved" and step["action"] == "publish":
        if visibility not in VISIBILITIES:
            raise ApprovalError(f"Set visibility to one of {VISIBILITIES} before publishing")
        final_practice = (practice or tool["practice"] or "").strip() or None
        if visibility == "practice-only" and not final_practice:
            raise ApprovalError("Name the practice for a practice-only tool")
        updates["visibility"] = visibility
        updates["practice"] = final_practice if visibility == "practice-only" else tool["practice"]
        detail = f"published as {visibility}" + (
            f" ({final_practice})" if visibility == "practice-only" else "")

    conn.execute(
        "INSERT INTO approvals (tool_id, position, step_name, approver_id, decision, comment, "
        "detail, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (tool_id, step["position"], step["name"], user_id, decision, comment, detail, now()),
    )
    if decision == "rejected":
        updates["status"] = "rejected"
    elif current_step(conn, tool_id) is None:
        updates["status"] = "published"
    if updates:
        sets = ", ".join(f"{col} = ?" for col in updates)
        conn.execute(f"UPDATE tools SET {sets} WHERE id = ?", (*updates.values(), tool_id))
    conn.commit()
    return get_tool(conn, tool_id)
