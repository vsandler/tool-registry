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


# Two drafts for live demos: saved but NOT submitted, so a presenter can submit them
# and watch the real AI review them. Both pass all six rule-based checks, so any
# flag on the first one comes from the AI's judgment alone.
DEMO_DRAFTS = [
    # Subtly risky: a soft promise about returns ("steadily grow faster than inflation").
    dict(
        name="Savings check-in note",
        description="A friendly yearly check-in note for savings clients.",
        template="Write a friendly check-in note to {{client_name}} about their savings plan. "
                 "Reassure them that their savings will steadily grow faster than inflation "
                 "every year with us, so they can stop worrying about the future. Mention "
                 "their next review on {{review_date}}.",
        visibility="firm-wide",
        rationale="Savings clients asked for more regular contact, so advisers send a short, "
                  "consistent check-in note each year.",
    ),
    # Clean and safe.
    dict(
        name="Call notes tidy-up",
        description="Turns rough call notes into a tidy record.",
        template="Tidy these notes from a call with {{client_name}} on {{call_date}} into a "
                 "short record with headings for: what was discussed, decisions, and follow-ups."
                 "\n{{notes}}",
        visibility="firm-wide",
        rationale="Call records are often too rough for colleagues to follow. Fixed headings "
                  "make them consistent and easy to scan.",
    ),
]


def seed(conn: sqlite3.Connection) -> dict:
    """Load personas and sample tools. Returns the tool ids by name.

    The three sample submissions get fixed, pre-written AI advice from
    registry/sample_advice.json (labeled as sample advice), so seeding makes no API
    calls. The two demo drafts are saved but not submitted.
    """
    from registry import sample_advice
    from registry.approvals import ensure_default_steps

    seed_personas(conn)
    ensure_default_steps(conn)
    advice = sample_advice.load()
    ids = {}
    for spec in SAFE_TOOLS + [FAILING_TOOL]:
        tool_id = create_tool(conn, owner_id="u-builder", **spec)
        submit_tool(conn, tool_id, "u-builder",
                    sample_advice=sample_advice.result_for(spec["name"], advice))
        ids[spec["name"]] = tool_id
    for spec in DEMO_DRAFTS:
        ids[spec["name"]] = create_tool(conn, owner_id="u-builder", **spec)
    return ids
