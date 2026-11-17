"""Rule-based checks run on every submission.

Checks only *flag* problems for a human. Nothing is auto-rejected (BRIEF.md
"Success Metrics"): a flagged tool still goes into review, with its flags attached.
"""

import re
import sqlite3
from dataclasses import dataclass

from registry.tools import find_variables, now

MIN_RATIONALE_LENGTH = 20

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\(\d{3}\)\s?|\b\d{3}[-.\s])\d{3}[-.\s]\d{4}\b")
ACCOUNT_NUMBER_PATTERN = re.compile(r"\b\d{8,}\b")


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str


def check_variables_match(tool: dict, conn: sqlite3.Connection) -> CheckResult:
    """Every {{blank}} in the template is declared, and every declared one is used."""
    used = set(find_variables(tool["template"]))
    declared = set(tool["variables"])
    undeclared = sorted(used - declared)
    unused = sorted(declared - used)
    if not undeclared and not unused:
        return CheckResult("variables_match", True, "Template variables match the declared list.")
    parts = []
    if undeclared:
        parts.append(f"used but not declared: {', '.join(undeclared)}")
    if unused:
        parts.append(f"declared but not used: {', '.join(unused)}")
    return CheckResult("variables_match", False, "Template variables " + "; ".join(parts) + ".")


def check_no_client_data(tool: dict, conn: sqlite3.Connection) -> CheckResult:
    """Templates must be stored clean: no emails, phone numbers or account numbers."""
    text = "\n".join([tool["name"], tool["description"], tool["template"], tool["rationale"]])
    found = []
    if EMAIL_PATTERN.search(text):
        found.append("an email address")
    if PHONE_PATTERN.search(text):
        found.append("a phone number")
    if ACCOUNT_NUMBER_PATTERN.search(text):
        found.append("a long number (possible account number)")
    if not found:
        return CheckResult("no_client_data", True, "No client data found.")
    return CheckResult(
        "no_client_data", False,
        f"Possible client data: {', '.join(found)}. Replace it with a {{{{variable}}}}.",
    )


def check_has_rationale(tool: dict, conn: sqlite3.Connection) -> CheckResult:
    """Each tool keeps a short record of why it was built that way."""
    if len(tool["rationale"].strip()) >= MIN_RATIONALE_LENGTH:
        return CheckResult("has_rationale", True, "Rationale recorded.")
    return CheckResult(
        "has_rationale", False,
        f"Add a short note (at least {MIN_RATIONALE_LENGTH} characters) on why the tool "
        "was built this way.",
    )


def check_owner_active(tool: dict, conn: sqlite3.Connection) -> CheckResult:
    """No orphaned tools: the owner must be a current user."""
    owner = conn.execute("SELECT active FROM users WHERE id = ?", (tool["owner_id"],)).fetchone()
    if owner is not None and owner["active"]:
        return CheckResult("owner_active", True, "Owner is a current user.")
    return CheckResult("owner_active", False, "Owner is no longer active. Assign a new owner.")


def check_practice_for_practice_only(tool: dict, conn: sqlite3.Connection) -> CheckResult:
    """A practice-only tool must say which practice it belongs to."""
    if tool["visibility"] != "practice-only" or (tool["practice"] or "").strip():
        return CheckResult("practice_set", True, "Visibility label is complete.")
    return CheckResult("practice_set", False, "Practice-only tools must name their practice.")


def check_unique_name(tool: dict, conn: sqlite3.Connection) -> CheckResult:
    """Avoid building the same tool twice: flag a name already in the catalogue."""
    clash = conn.execute(
        "SELECT id FROM tools WHERE lower(trim(name)) = lower(trim(?)) AND id != ? "
        "AND status IN ('in_review', 'published')",
        (tool["name"], tool["id"]),
    ).fetchone()
    if clash is None:
        return CheckResult("unique_name", True, "No other tool has this name.")
    return CheckResult(
        "unique_name", False,
        f"A tool with this name already exists (tool {clash['id']}). Reuse it instead?",
    )


# How each check is named on screen.
CHECK_LABELS = {
    "variables_match": "Blanks match",
    "no_client_data": "No client data",
    "has_rationale": "Reason recorded",
    "owner_active": "Owner is current",
    "practice_set": "Practice named",
    "unique_name": "Unique name",
}

# A tip for each check, shown with a flag so the builder knows how to avoid it next time.
CHECK_TIPS = {
    "variables_match": "List every blank the template uses, and remove any it doesn't. "
                       "Tools made on the Submit form get this list from the template "
                       "automatically.",
    "no_client_data": "Replace real emails, phone numbers and account numbers with blanks, "
                      "so the stored template holds no client details.",
    "has_rationale": f"Write a sentence or two (at least {MIN_RATIONALE_LENGTH} characters) "
                     "on why the tool is built this way, for example why these steps or "
                     "this wording.",
    "owner_active": "Ask an admin to hand the tool to a current owner.",
    "practice_set": "For a practice-only tool, choose the practice it belongs to.",
    "unique_name": "Look for the existing tool in the Catalog and reuse it, or choose a "
                   "name that says how yours is different.",
}

ALL_CHECKS = [
    check_variables_match,
    check_no_client_data,
    check_has_rationale,
    check_owner_active,
    check_practice_for_practice_only,
    check_unique_name,
]


def run_checks(conn: sqlite3.Connection, tool: dict) -> list[CheckResult]:
    return [check(tool, conn) for check in ALL_CHECKS]


def save_check_results(conn: sqlite3.Connection, tool_id: int, results: list[CheckResult]) -> None:
    conn.execute("DELETE FROM check_results WHERE tool_id = ?", (tool_id,))
    stamp = now()
    conn.executemany(
        "INSERT INTO check_results (tool_id, check_name, passed, message, checked_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [(tool_id, r.name, int(r.passed), r.message, stamp) for r in results],
    )


def get_check_results(conn: sqlite3.Connection, tool_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT check_name, passed, message FROM check_results WHERE tool_id = ? ORDER BY id",
        (tool_id,),
    )
    return [{"name": r["check_name"], "label": CHECK_LABELS.get(r["check_name"], r["check_name"]),
             "passed": bool(r["passed"]), "message": r["message"],
             "tip": CHECK_TIPS.get(r["check_name"], "")}
            for r in rows]
