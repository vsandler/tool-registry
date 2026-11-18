"""Tools: reusable templates with {{variables}} and a visibility label."""

import json
import re
import sqlite3
from datetime import datetime, timezone

from registry.personas import SUBMIT_REFUSED_MESSAGE, SUBMIT_ROLES, get_user, practice_names

VISIBILITIES = ("practice-only", "firm-wide")

# The visibility choices on the Submit form, in the order shown. `asks_practice` says
# whether that choice needs a practice, so the screen knows when to show the box.
VISIBILITY_OPTIONS = [
    {"value": "firm-wide", "label": "Firm-wide", "asks_practice": False},
    {"value": "practice-only", "label": "Practice-only", "asks_practice": True},
]

RATIONALE_REQUIRED = "Explain why you built it this way."

# The Submit form's boxes, in order: on-screen label, whether the back end refuses a
# submission without it (`required`), and a short hint shown under the box.
# tests/test_submit_screen.py checks `required` matches what is actually refused.
FORM_FIELDS = [
    {"name": "name", "label": "Name", "required": True,
     "hint": "A short, clear name people will recognise, such as \"Meeting summary\"."},
    {"name": "description", "label": "Description", "required": False,
     "hint": "One sentence on what the tool does."},
    {"name": "template", "label": "Template", "required": True,
     "hint": "The reusable text. Put anything that changes for each use, such as a client's "
             "name, in double curly braces: {{client_name}}."},
    {"name": "visibility", "label": "Who can see it", "required": True,
     "hint": "Firm-wide: everyone in the firm. Practice-only: one practice."},
    {"name": "practice", "label": "Practice", "required": False,
     "hint": "Which practice a practice-only tool belongs to."},
    {"name": "rationale", "label": "Why did you build it this way?", "required": True,
     "hint": "A sentence or two on why you built it this way helps reviewers."},
]

# A template variable looks like {{client_name}}: letters, digits, underscores.
VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class ToolError(ValueError):
    """Raised when a tool request can't be carried out (bad input)."""


class NotFound(ToolError):
    """The tool or user doesn't exist."""


class NotAllowed(ToolError):
    """The person isn't allowed to do this."""


class InputError(ToolError):
    """Input that can't be used. `fields` names the form boxes the message is about,
    so the screen can show it next to them; `messages`, when given, has one message
    per box, for showing next to each."""

    def __init__(self, message: str, fields: list[str], messages: dict[str, str] | None = None):
        super().__init__(message)
        self.fields = fields
        self.messages = messages


def refuse_if_problems(problems: dict[str, str]) -> None:
    """Raise one InputError listing every problem ({box: message}), if there are any."""
    if problems:
        raise InputError(" ".join(problems.values()), list(problems), dict(problems))


def input_problems(*, name, template, visibility, rationale=None) -> dict[str, str]:
    """What's wrong with a new tool's input, box by box. The rationale is checked only
    when one is passed (that is, when submitting, not when saving a draft)."""
    problems = {}
    if not (name or "").strip():
        problems["name"] = "Give the tool a name."
    if not (template or "").strip():
        problems["template"] = "Add the template text."
    if visibility not in VISIBILITIES:
        labels = " or ".join(o["label"] for o in VISIBILITY_OPTIONS)
        problems["visibility"] = f"Choose who can see the tool: {labels}."
    if rationale is not None and not rationale.strip():
        problems["rationale"] = RATIONALE_REQUIRED
    return problems


def unknown_practice_message(conn: sqlite3.Connection) -> str:
    """"Choose a practice from the list: Audit or Tax." (REVIEW.md finding 1)."""
    names = practice_names(conn)
    listed = " or ".join(names) if len(names) <= 2 else (
        ", ".join(names[:-1]) + " or " + names[-1])
    return f"Choose a practice from the list: {listed}."


def practice_problems(conn: sqlite3.Connection, *, visibility, practice) -> dict[str, str]:
    """A practice-only tool's practice must be one from the list (the practices people
    belong to). A blank one is allowed here: the checks flag it instead. A firm-wide
    tool stores no practice, so what was typed doesn't matter."""
    practice = (practice or "").strip()
    if visibility == "practice-only" and practice and practice not in practice_names(conn):
        return {"practice": unknown_practice_message(conn)}
    return {}


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


# --- personalising from the catalogue ------------------------------------------------

class PersonaliseError(InputError):
    """Values for a personal copy that can't be used. `fields` names the blanks."""


def blank_label(name: str) -> str:
    """How a blank is named on screen: "client_name" -> "Client name"."""
    words = name.replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def blanks_for(template: str) -> list[dict]:
    """The blanks a person fills in, read from the template itself (the same ones
    `render` fills), with an on-screen label for each."""
    return [{"name": n, "label": blank_label(n)} for n in find_variables(template)]


def personalise(template: str, values: dict[str, str]) -> str:
    """Fill in a template for someone's own copy. Every blank needs a value with
    something other than spaces in it, and every value must be for a real blank.
    Nothing is saved: the values may be client details."""
    names = find_variables(template)
    unknown = [k for k in values if k not in names]
    if unknown:
        raise PersonaliseError(f"This tool has no blank called: {', '.join(unknown)}.", unknown)
    missing = [n for n in names if not str(values.get(n, "")).strip()]
    if missing:
        labels = ", ".join(blank_label(n) for n in missing)
        raise PersonaliseError(f"Fill in every blank before downloading your copy: {labels}.",
                               missing)
    return render(template, values)


def download_filename(tool_name: str) -> str:
    """A safe file name for a personal copy, from the tool's name only (never from the
    values typed in): "Meeting summary" -> "meeting-summary.txt"."""
    slug = re.sub(r"[^a-z0-9]+", "-", tool_name.lower()).strip("-")
    return f"{slug or 'personalised-tool'}.txt"


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
    An empty name or template, or an unknown visibility, is refused (InputError, naming
    the boxes). Everything else, such as a missing rationale or practice, is saved and
    left to the rule-based checks to flag: flags don't block submission.
    The name and practice are trimmed; a blank practice, or any practice on a
    firm-wide tool, is stored as None.
    """
    check_can_submit(conn, owner_id)
    refuse_if_problems({
        **input_problems(name=name, template=template, visibility=visibility),
        **practice_problems(conn, visibility=visibility, practice=practice),
    })
    name = name.strip()
    practice = (practice or "").strip() or None
    if visibility == "firm-wide":
        practice = None
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


def check_can_submit(conn: sqlite3.Connection, user_id: str) -> None:
    """Only the roles in SUBMIT_ROLES may save or submit tools (Tool users can't)."""
    user = get_user(conn, user_id)
    if user is not None and user["role"] not in SUBMIT_ROLES:
        raise NotAllowed(SUBMIT_REFUSED_MESSAGE)


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

    A rationale is required (DECISIONS.md #15): an empty one is refused before any
    check or AI call runs. The seed's sample submissions are exempt: they stand for
    submissions made before this rule, so the demo keeps its tool with no rationale.
    """
    check_can_submit(conn, user_id)
    # Imported here to avoid circular imports (both modules import from this one).
    from registry import agent
    from registry.checks import get_check_results, run_checks, save_check_results

    tool = get_tool(conn, tool_id)
    if tool is None:
        raise NotFound(f"Tool {tool_id} not found")
    if tool["owner_id"] != user_id:
        raise NotAllowed("Only the tool's owner can submit it")
    if tool["status"] != "draft":
        raise NotAllowed(f"Only drafts can be submitted; this tool is {tool['status']}")
    if sample_advice is None and not tool["rationale"].strip():
        refuse_if_problems({"rationale": RATIONALE_REQUIRED})
    results = run_checks(conn, tool)
    if sample_advice is None:
        ai_result = agent.review_for_submission(tool)  # never raises
    else:
        ai_result = sample_advice
    save_check_results(conn, tool_id, results)
    agent.save_ai_review(conn, tool_id, ai_result, is_sample=sample_advice is not None)
    conn.execute("UPDATE tools SET status = 'in_review', submitted_at = ? WHERE id = ?",
                 (now(), tool_id))
    conn.commit()
    return {
        "tool": get_tool(conn, tool_id),
        "checks": get_check_results(conn, tool_id),  # as saved, with on-screen labels
        "flagged": any(not r.passed for r in results),
        "ai_review": agent.get_ai_review(conn, tool_id),
    }


def create_and_submit(conn: sqlite3.Connection, owner_id: str, **fields) -> dict:
    """The Submit form's one call: check everything first (reporting every problem
    at once), so a refusal saves nothing, then save the tool and send it for review."""
    refuse_if_problems({
        **input_problems(
            name=fields.get("name"), template=fields.get("template"),
            visibility=fields.get("visibility"), rationale=fields.get("rationale") or ""),
        **practice_problems(conn, visibility=fields.get("visibility"),
                            practice=fields.get("practice")),
    })
    tool_id = create_tool(conn, owner_id=owner_id, **fields)
    return submit_tool(conn, tool_id, owner_id)


def list_tools(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = conn.execute("SELECT id FROM tools WHERE status = ? ORDER BY id", (status,))
    else:
        rows = conn.execute("SELECT id FROM tools ORDER BY id")
    return [get_tool(conn, r["id"]) for r in rows.fetchall()]
