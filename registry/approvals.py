"""The approval flow (DECISIONS.md #1 and #11).

The shared order is stored as an ordered list of steps in the `approval_steps`
table, so a configurable order (BACKLOG.md) can replace it later without a rewrite.
Each step names the role that decides it and what deciding it does:

  1. route   - Super admin approves and sends it to one or more specialist areas
  2. review  - a Specialist reviewer from that area approves (one step per area)
  3. publish - back to the Super admin, who sets visibility and publishes

When a tool is routed, it gets its own list of steps (`tool_steps`): the shared
list, with the review step repeated once per chosen area, in the chosen order.
Tools not yet routed, or routed before this existed, use the shared list.

Rules:
  - Steps happen strictly in order.
  - Only the role named on the current step can decide it; for a review step,
    only a specialist from that step's area.
  - Nobody can approve or reject their own tool, admins included.
  - The same Super admin may decide steps 1 and 3, but a step marked
    `different_person` (the specialist review) must be decided by someone who
    decided no other step of this tool.
  - Every decision is recorded in the history and never changed.
  - A rejection at any step is final (for now); publishing ends the review.
"""

import sqlite3

from registry.personas import (
    ROLES,
    SPECIALIST_AREAS,
    area_phrase,
    get_user,
    practice_names,
    role_phrase,
)
from registry.tools import (
    VISIBILITIES,
    VISIBILITY_OPTIONS,
    NotAllowed,
    NotFound,
    get_tool,
    now,
)


class ApprovalError(NotAllowed):
    """Raised when an approval decision isn't allowed."""


class ApprovalInputError(ApprovalError):
    """The decision is missing something or has a bad value (e.g. no route area)."""


class ApprovalNotFound(ApprovalError, NotFound):
    """The tool or user in the decision doesn't exist."""


class CommentRequired(ApprovalInputError):
    """A rejection needs a comment. `field` tells a form which box the message is for."""

    field = "comment"


# A rejection is final, so the builder must be told why (DECISIONS.md #12).
MIN_REJECT_COMMENT = 10
REJECT_COMMENT_MESSAGE = (
    f"Add a comment of at least {MIN_REJECT_COMMENT} characters explaining why you're "
    "rejecting this tool. The builder will see it."
)

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
        raise ApprovalInputError("The approval order needs at least one step")
    for step in steps:
        if step["approver_role"] not in ROLES:
            raise ApprovalInputError(f"Unknown role {step['approver_role']!r}")
        if step["action"] not in ACTIONS:
            raise ApprovalInputError(f"Unknown action {step['action']!r}")
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
    return [{**dict(r), "detail_label": readable_detail(r["detail"])} for r in rows]


def readable_detail(detail: str) -> str:
    """A history entry's stored `detail` in the names people see, for the screens:
    "routed to technology, then marketing" -> "Routed to AI enablement (technology),
    then Marketing"; "published as practice-only (Tax)" -> "Published as Practice-only
    (Tax)". The stored text itself is never changed."""
    detail = detail or ""
    if detail.startswith("routed to "):
        areas = detail[len("routed to "):].split(", then ")
        return "Routed to " + ", then ".join(SPECIALIST_AREAS.get(a, a) for a in areas)
    if detail.startswith("published as "):
        rest = detail[len("published as "):]
        value, _, practice = rest.partition(" (")
        labels = {o["value"]: o["label"] for o in VISIBILITY_OPTIONS}
        return f"Published as {labels.get(value, value)}" + (f" ({practice}" if practice else "")
    return detail[:1].upper() + detail[1:]


def get_tool_steps(conn: sqlite3.Connection, tool_id: int) -> list[dict]:
    """This tool's approval steps, in order. Each step has an `area`: the specialist
    area for a review step (None if not routed yet), and None for other steps.

    A routed tool has its own list. Otherwise the shared list is used; for a tool
    routed before multi-area routing existed, its review step takes the tool's
    single `routed_to` area.
    """
    rows = conn.execute(
        "SELECT position, name, approver_role, action, area, different_person "
        "FROM tool_steps WHERE tool_id = ? ORDER BY position", (tool_id,)).fetchall()
    if rows:
        return [{**dict(r), "different_person": bool(r["different_person"])} for r in rows]
    tool = get_tool(conn, tool_id)
    routed_to = tool["routed_to"] if tool else None
    return [{**s, "area": routed_to if s["action"] == "review" else None}
            for s in get_steps(conn)]


def current_step(conn: sqlite3.Connection, tool_id: int) -> dict | None:
    """The next step waiting for a decision, or None if the review is over."""
    tool = get_tool(conn, tool_id)
    if tool is None or tool["status"] != "in_review":
        return None
    done = {h["position"] for h in get_history(conn, tool_id) if h["decision"] == "approved"}
    for step in get_tool_steps(conn, tool_id):
        if step["position"] not in done:
            return step
    return None


def _routed_areas(steps: list[dict]) -> list[str]:
    return [s["area"] for s in steps if s["action"] == "review" and s["area"]]


def _check_areas(route_to) -> list[str]:
    """Turn route_to (one area as text, or a list of areas in order) into a checked list."""
    areas = [route_to] if isinstance(route_to, str) or route_to is None else list(route_to)
    choices = _one_of(SPECIALIST_AREAS.values())
    if not areas:
        raise ApprovalInputError(f"Choose at least one specialist area to route to: {choices}.")
    for area in areas:
        if area not in SPECIALIST_AREAS:
            raise ApprovalInputError(f"Choose a specialist area to route to: {choices}.")
    repeated = [a for a in SPECIALIST_AREAS if areas.count(a) > 1]
    if repeated:
        raise ApprovalInputError(
            "Each specialist area can only be chosen once. Picked more than once: "
            f"{', '.join(SPECIALIST_AREAS[a] for a in repeated)}.")
    return areas


def _one_of(labels) -> str:
    """"A, B or C", for a message listing the choices."""
    labels = list(labels)
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]


def _expand_for_areas(steps: list[dict], route_position: int, areas: list[str]) -> list[dict]:
    """The tool's own step list: every review step after the route step becomes one
    review step per chosen area, in order. Positions are renumbered from 1."""
    expanded = []
    for step in steps:
        if step["action"] == "review" and step["position"] > route_position:
            for area in areas:
                expanded.append({**step, "name": f"{SPECIALIST_AREAS[area]} review",
                                 "area": area})
        else:
            expanded.append({**step, "area": step["area"] if step["action"] == "review" else None})
    return [{**s, "position": i} for i, s in enumerate(expanded, start=1)]


def _save_tool_steps(conn: sqlite3.Connection, tool_id: int, steps: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO tool_steps (tool_id, position, name, approver_role, action, area, "
        "different_person) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(tool_id, s["position"], s["name"], s["approver_role"], s["action"], s["area"],
          int(s["different_person"])) for s in steps],
    )


def _check_turn(conn: sqlite3.Connection, tool: dict, user: sqlite3.Row) -> dict:
    """Is it this person's turn to decide this tool's current step? The one place
    the "who may act" rules live: decide() and my_action() both use it.

    Returns {"step", "steps", "refusal"}. `refusal` is None when they may decide,
    otherwise (code, message): a short code my_action() turns into a plain sentence,
    and the message decide() raises. The order of the checks matters: no
    self-approval comes first, so the reason is clear whatever the role.
    """
    steps = get_tool_steps(conn, tool["id"])
    step = current_step(conn, tool["id"])
    found = {"step": step, "steps": steps, "refusal": None}

    def refuse(code, message):
        return {**found, "refusal": (code, message)}

    if tool["owner_id"] == user["id"]:
        return refuse("own_tool", "You can't approve or reject your own tool, even as an admin")
    if tool["status"] != "in_review":
        return refuse("not_in_review", f"This tool isn't in review (it is {tool['status']})")
    if not steps:
        return refuse("no_order", "No approval order has been set up")
    if user["role"] != step["approver_role"]:
        return refuse("wrong_role",
                      f"Step {step['position']} ({step['name']}) must be decided by "
                      f"{role_phrase(step['approver_role'])}, not {role_phrase(user['role'])}")
    if step["action"] == "review" and user["specialty"] != step["area"]:
        if step["area"] is None:
            return refuse("wrong_area", "This tool hasn't been routed to a specialist area yet")
        routed = ", then ".join(SPECIALIST_AREAS.get(a, a) for a in _routed_areas(steps))
        return refuse("wrong_area",
                      f"Step {step['position']} is the "
                      f"{SPECIALIST_AREAS.get(step['area'], step['area'])} review (this tool "
                      f"was routed to {routed}); {area_phrase(user['specialty'])} "
                      "can't decide it")
    history = get_history(conn, tool["id"])
    if step["different_person"] and any(h["approver_id"] == user["id"] for h in history):
        return refuse("already_decided",
                      "This step must be decided by someone who hasn't decided another "
                      "step of this tool")
    return found


_NOT_IN_REVIEW = {
    "draft": "This tool hasn't been submitted yet.",
    "rejected": "This tool was rejected, so the review is over.",
    "published": "Published. Nothing left to decide.",
}


def my_action(conn: sqlite3.Connection, tool_id: int, user_id: str) -> dict | None:
    """What the persona viewing a tool can do with it right now, for the screens.

    {"can_decide", "reason", "needs", "choices", "step_position", "step_name", "final",
     "reject_comment_min"}. `reason` is a plain sentence when they can't decide;
    `needs` says what deciding asks for ("areas" to route, "visibility" to publish),
    and `choices` lists what to pick from (None when nothing needs picking).
    Uses exactly the same rules as decide(). None if the tool doesn't exist.
    """
    tool = get_tool(conn, tool_id)
    if tool is None:
        return None
    user = get_user(conn, user_id)
    if user is None:
        return {"can_decide": False, "reason": "Pick a persona first.", "needs": None,
                "choices": None, "step_position": None, "step_name": None, "final": False,
                "reject_comment_min": MIN_REJECT_COMMENT}
    turn = _check_turn(conn, tool, user)
    step, steps = turn["step"], turn["steps"]
    reason = None
    if turn["refusal"]:
        code = turn["refusal"][0]
        if code == "own_tool":
            reason = "You built this tool, so you can't approve or reject it."
        elif code == "not_in_review":
            reason = _NOT_IN_REVIEW.get(tool["status"], "This tool isn't in review.")
        elif code == "no_order":
            reason = "No approval order has been set up."
        elif code == "already_decided":
            reason = ("You've already decided another step of this tool, "
                      "so someone else must decide this one.")
        else:  # wrong_role, wrong_area
            reason = f"Waiting for {_waiting_for(step)}."
    needs = None
    if step is not None and reason is None:
        needs = {"route": "areas", "publish": "visibility"}.get(step["action"])
    return {
        "can_decide": reason is None,
        "reason": reason,
        "needs": needs,
        "choices": _choices(conn, tool, needs),
        "step_position": step["position"] if step else None,
        "step_name": step["name"] if step else None,
        "final": bool(step and steps and step["position"] == steps[-1]["position"]),
        "reject_comment_min": MIN_REJECT_COMMENT,
    }


def get_rejection(conn: sqlite3.Connection, tool_id: int) -> dict | None:
    """Who rejected the tool, when, at which step and why. None if not rejected."""
    rejected = [h for h in get_history(conn, tool_id) if h["decision"] == "rejected"]
    if not rejected:
        return None
    r = rejected[-1]
    return {"by": r["approver_name"], "by_id": r["approver_id"], "at": r["decided_at"],
            "step_position": r["position"], "step_name": r["step_name"],
            "reason": r["comment"]}


def _waiting_for(step: dict) -> str:
    """Who the step is waiting for, using the names people see in the persona dropdown."""
    if step["action"] == "review":
        return area_phrase(step["area"]) if step["area"] else "a specialist (not routed yet)"
    return role_phrase(step["approver_role"])


def _choices(conn: sqlite3.Connection, tool: dict, needs: str | None) -> dict | None:
    """What the screen offers for this decision, so it never works out choices itself.
    Routing: every specialist area, in order. Publishing: the visibility options,
    the practices, and what the builder asked for, to start from."""
    if needs == "areas":
        return {"areas": [{"value": k, "label": v} for k, v in SPECIALIST_AREAS.items()]}
    if needs == "visibility":
        return {"visibilities": VISIBILITY_OPTIONS, "practices": practice_names(conn),
                "requested": {"visibility": tool["visibility"], "practice": tool["practice"]}}
    return None


def get_progress(conn: sqlite3.Connection, tool_id: int) -> list[dict]:
    """Every approval step of this tool, for the progress line (DECISIONS.md #10).

    Each step has a `status`: "done" (approved), "rejected", "waiting" (not decided
    yet) or "not_reached" (after a rejection). `current` marks the step waiting now,
    `final` marks the last step, and decided steps say who decided them and when.
    A not-reached step's `skipped_reason` says why, for the screen to show as-is.
    """
    tool = get_tool(conn, tool_id)
    if tool is None:
        return []
    history = {h["position"]: h for h in get_history(conn, tool_id)}
    now_step = current_step(conn, tool_id)
    steps = get_tool_steps(conn, tool_id)
    rejected_at = next((h["position"] for h in history.values()
                        if h["decision"] == "rejected"), None)
    progress = []
    for step in steps:
        decided = history.get(step["position"])
        if decided and decided["decision"] == "approved":
            status = "done"
        elif decided:
            status = "rejected"
        elif tool["status"] == "rejected":
            status = "not_reached"
        else:
            status = "waiting"
        progress.append({
            **step,
            "status": status,
            "current": now_step is not None and step["position"] == now_step["position"],
            "final": step["position"] == steps[-1]["position"],
            "decided_by": decided["approver_name"] if decided else None,
            "decided_by_id": decided["approver_id"] if decided else None,
            "decided_at": decided["decided_at"] if decided else None,
            "comment": decided["comment"] if decided else "",
            "detail": decided["detail"] if decided else "",
            "waiting_for": _waiting_for(step) if status == "waiting" else None,
            # Once fix-and-resubmit exists, this becomes "On hold: waiting for the
            # builder to fix and resubmit" (BACKLOG.md).
            "skipped_reason": (f"Skipped: rejected at step {rejected_at}"
                               if status == "not_reached" else None),
        })
    return progress


def decide(
    conn: sqlite3.Connection,
    tool_id: int,
    user_id: str,
    decision: str,
    comment: str = "",
    *,
    route_to: str | list[str] | None = None,
    visibility: str | None = None,
    practice: str | None = None,
) -> dict:
    """Record one decision on the tool's current step. Returns the updated tool.

    - Approving a `route` step needs `route_to`: one specialist area, or a list of
      areas in the order they should review. Each becomes its own review step.
    - Approving a `publish` step needs `visibility`; practice-only also needs a
      practice (given here, or already on the tool).
    """
    if decision not in DECISIONS:
        raise ApprovalInputError(f"Decision must be one of {DECISIONS}")
    tool = get_tool(conn, tool_id)
    if tool is None:
        raise ApprovalNotFound(f"Tool {tool_id} not found")
    user = get_user(conn, user_id)
    if user is None:
        raise ApprovalNotFound(f"User {user_id} not found")

    turn = _check_turn(conn, tool, user)
    if turn["refusal"]:
        raise ApprovalError(turn["refusal"][1])
    step, steps = turn["step"], turn["steps"]

    comment = (comment or "").strip()
    if decision == "rejected" and len(comment) < MIN_REJECT_COMMENT:
        raise CommentRequired(REJECT_COMMENT_MESSAGE)

    detail = ""
    updates: dict = {}
    new_tool_steps: list[dict] = []
    if decision == "approved" and step["action"] == "route":
        areas = _check_areas(route_to)
        new_tool_steps = _expand_for_areas(steps, step["position"], areas)
        # routed_to keeps the first area, for older code and tools; the full,
        # ordered list lives in the tool's own steps.
        updates["routed_to"] = areas[0]
        detail = "routed to " + ", then ".join(areas)
    elif decision == "approved" and step["action"] == "publish":
        if visibility not in VISIBILITIES:
            raise ApprovalInputError("Choose a visibility before publishing: "
                                     f"{_one_of(o['label'] for o in VISIBILITY_OPTIONS)}.")
        final_practice = (practice or tool["practice"] or "").strip() or None
        if visibility == "practice-only" and not final_practice:
            raise ApprovalInputError("Choose a practice for a Practice-only tool.")
        updates["visibility"] = visibility
        updates["practice"] = final_practice if visibility == "practice-only" else tool["practice"]
        detail = f"published as {visibility}" + (
            f" ({final_practice})" if visibility == "practice-only" else "")

    conn.execute(
        "INSERT INTO approvals (tool_id, position, step_name, approver_id, decision, comment, "
        "detail, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (tool_id, step["position"], step["name"], user_id, decision, comment, detail, now()),
    )
    if new_tool_steps:
        _save_tool_steps(conn, tool_id, new_tool_steps)
    if decision == "rejected":
        updates["status"] = "rejected"
    elif current_step(conn, tool_id) is None:
        updates["status"] = "published"
    if updates:
        sets = ", ".join(f"{col} = ?" for col in updates)
        conn.execute(f"UPDATE tools SET {sets} WHERE id = ?", (*updates.values(), tool_id))
    conn.commit()
    return get_tool(conn, tool_id)
