"""Rejections need a comment of at least 10 characters, and every rejected tool shows
who rejected it, when, at which step and why (DECISIONS.md #12)."""

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app
from registry.approvals import (
    REJECT_COMMENT_MESSAGE,
    ApprovalError,
    ApprovalInputError,
    decide,
    ensure_default_steps,
    get_history,
    get_rejection,
)
from registry.tools import create_tool, get_tool, submit_tool

SUPER = "u-super-admin"
COMPLIANCE = "u-specialist"
MARKETING = "u-specialist-marketing"

EXPECTED_MESSAGE = ("Add a comment of at least 10 characters explaining why you're "
                    "rejecting this tool. The builder will see it.")


@pytest.fixture
def flow(conn):
    ensure_default_steps(conn)
    return conn


def submitted_tool(conn, owner="u-builder"):
    tid = create_tool(conn, name=f"Reject test by {owner}", template="Hi {{name}}",
                      owner_id=owner, visibility="firm-wide",
                      rationale="A clear, reusable greeting.")
    submit_tool(conn, tid, owner)
    return tid


# --- the comment rule -------------------------------------------------------------------

def test_message_is_exactly_the_agreed_wording():
    assert REJECT_COMMENT_MESSAGE == EXPECTED_MESSAGE


@pytest.mark.parametrize("comment", [
    "",                    # empty
    "          ",          # spaces only
    "Too vague",           # 9 characters
    "     Too vague    ",  # 9 characters once the spaces around it are ignored
])
def test_short_or_missing_comment_is_refused(flow, comment):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalInputError) as refused:
        decide(flow, tid, SUPER, "rejected", comment)
    assert str(refused.value) == EXPECTED_MESSAGE
    assert get_tool(flow, tid)["status"] == "in_review"  # nothing changed
    assert get_history(flow, tid) == []


def test_exactly_10_characters_is_accepted(flow):
    tid = submitted_tool(flow)
    assert len("Not useful") == 10
    decide(flow, tid, SUPER, "rejected", "Not useful")
    assert get_tool(flow, tid)["status"] == "rejected"


def test_spaces_around_the_comment_are_trimmed_when_saved(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, SUPER, "rejected", "   Not useful   ")
    assert get_history(flow, tid)[0]["comment"] == "Not useful"


def test_approving_still_needs_no_comment(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, SUPER, "approved", "", route_to="compliance")
    assert get_tool(flow, tid)["status"] == "in_review"


def test_self_approval_is_still_refused_first(flow):
    """The owner gets the 'your own tool' reason, not a comment-length one."""
    tid = submitted_tool(flow, owner=SUPER)
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(flow, tid, SUPER, "rejected", "")


def test_wrong_persona_is_still_refused_first(flow):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError, match="must be decided by a super_admin"):
        decide(flow, tid, COMPLIANCE, "rejected", "")


# --- the rejection note ----------------------------------------------------------------------

def test_rejection_records_who_when_which_step_and_why(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, SUPER, "approved", route_to=["compliance", "marketing"])
    decide(flow, tid, COMPLIANCE, "approved")
    decide(flow, tid, MARKETING, "rejected", "Promises returns in the second paragraph")
    rejection = get_rejection(flow, tid)
    assert rejection["by"] == "Quinn Harrow"
    assert rejection["by_id"] == MARKETING
    assert rejection["at"]
    assert rejection["step_position"] == 3
    assert rejection["step_name"] == "Marketing review"
    assert rejection["reason"] == "Promises returns in the second paragraph"


def test_tool_that_is_not_rejected_has_no_rejection_note(flow):
    tid = submitted_tool(flow)
    assert get_rejection(flow, tid) is None


# --- through the API --------------------------------------------------------------------------

@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def api_tool(client):
    headers = {"X-Persona": "u-builder"}
    tid = client.post("/tools", headers=headers, json=dict(
        name="API reject tool", template="Hi {{name}}", visibility="firm-wide",
        rationale="A clear, reusable greeting.")).json()["id"]
    client.post(f"/tools/{tid}/submit", headers=headers)
    return tid


@pytest.mark.parametrize("comment", ["", "   ", "Too vague"])
def test_api_refuses_short_comment_with_the_plain_message(client, comment):
    tid = api_tool(client)
    r = client.post(f"/tools/{tid}/decisions", headers={"X-Persona": SUPER},
                    json={"decision": "rejected", "comment": comment})
    assert r.status_code == 400
    assert r.json() == {"detail": EXPECTED_MESSAGE, "field": "comment"}


def test_rejection_reason_appears_in_the_tool_details(client):
    tid = api_tool(client)
    r = client.post(f"/tools/{tid}/decisions", headers={"X-Persona": SUPER},
                    json={"decision": "rejected", "comment": "Duplicates an existing tool"})
    assert r.status_code == 200
    # The decision's own reply (what the Review queue detail panel shows next)...
    assert r.json()["rejection"]["reason"] == "Duplicates an existing tool"
    # ...the builder's view of the tool...
    builder = client.get(f"/tools/{tid}", headers={"X-Persona": "u-builder"}).json()
    assert builder["rejection"] == {**builder["rejection"], "by": "Riley Ashgrove",
                                    "step_position": 1, "reason": "Duplicates an existing tool"}
    # ...and the builder's own list of tools.
    mine = client.get("/my-tools", headers={"X-Persona": "u-builder"}).json()
    assert next(t for t in mine if t["id"] == tid)["rejection"]["reason"] == (
        "Duplicates an existing tool")


def test_tools_in_review_have_no_rejection_note(client):
    queue = client.get("/admin/review-queue", headers={"X-Persona": SUPER}).json()
    assert queue and all(t["rejection"] is None for t in queue)
