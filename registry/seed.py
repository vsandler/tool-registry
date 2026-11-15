"""Made-up sample data. Every person, client and number here is invented.

Includes one deliberately failing submission ("Client welcome letter") so the
checks have something to catch.
"""

import sqlite3

from registry.personas import seed_personas
from registry.tools import create_tool, submit_tool

SAFE_TOOLS = [
    dict(
        name="Meeting summary",
        description="Turns rough meeting notes into a short summary with actions.",
        template="Summarise these notes from the {{meeting_topic}} meeting in five bullet "
                 "points, then list actions with owners:\n{{notes}}",
        visibility="firm-wide",
        rationale="Five bullets keeps summaries skimmable; actions are listed separately "
                  "so they aren't lost.",
    ),
    dict(
        name="Engagement letter draft",
        description="First draft of a standard engagement letter.",
        template="Draft an engagement letter for {{client_name}} covering {{service}}, "
                  "starting {{start_date}}. Use plain English.",
        visibility="practice-only",
        practice="Tax",
        rationale="The client name and dates are blanks so the stored template never "
                  "holds client details.",
    ),
]

# The deliberately failing submission. It breaks four checks on purpose:
#   - a (made-up) client email and phone number pasted into the template
#   - {{tax_year}} used but not declared
#   - no rationale
#   - practice-only with no practice named
FAILING_TOOL = dict(
    name="Client welcome letter",
    description="Welcome letter for a new client.",
    template="Write a welcome letter to {{client_name}} for the {{tax_year}} tax year. "
             "Contact them at pat.example@example.com or (555) 010-0142.",
    variables=["client_name"],
    visibility="practice-only",
    practice=None,
    rationale="",
)


def seed(conn: sqlite3.Connection) -> dict:
    """Load personas and sample tools, and submit them all. Returns the tool ids."""
    from registry.approvals import ensure_default_steps

    seed_personas(conn)
    ensure_default_steps(conn)
    ids = {}
    for spec in SAFE_TOOLS + [FAILING_TOOL]:
        tool_id = create_tool(conn, owner_id="u-builder", **spec)
        submit_tool(conn, tool_id, "u-builder")
        ids[spec["name"]] = tool_id
    return ids
