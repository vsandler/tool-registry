"""Approval rules.

These tests set their own two-step order, so they test the rules themselves.
They don't depend on which roles the real default order uses (still an open
question; see STATUS.md).
"""

import pytest

from registry.approvals import ApprovalError, current_step, decide, get_history, get_steps, set_steps
from registry.tools import create_tool, get_tool, submit_tool

TEST_STEPS = [
    {"name": "First check", "approver_role": "super_admin"},
    {"name": "Second check", "approver_role": "practice_admin"},
]


@pytest.fixture
def flow(conn):
    set_steps(conn, TEST_STEPS)
    return conn


def submitted_tool(conn, owner="u-builder"):
    tid = create_tool(conn, name=f"Tool by {owner}", template="Hi {{name}}", owner_id=owner,
                      visibility="firm-wide", rationale="A clear, reusable greeting.")
    submit_tool(conn, tid, owner)
    return tid


# --- the order is stored as a list of steps ----------------------------------

def test_order_is_stored_as_ordered_list(flow):
    assert [(s["position"], s["approver_role"]) for s in get_steps(flow)] == [
        (1, "super_admin"), (2, "practice_admin")]


def test_order_rejects_unknown_role(conn):
    with pytest.raises(ApprovalError):
        set_steps(conn, [{"name": "X", "approver_role": "wizard"}])


def test_order_rejects_empty_list(conn):
    with pytest.raises(ApprovalError):
        set_steps(conn, [])


def test_no_order_set_up_is_refused(conn):
    tid = submitted_tool(conn)
    with pytest.raises(ApprovalError, match="No approval order"):
        decide(conn, tid, "u-super-admin", "approved")


# --- happy path and order ----------------------------------------------------

def test_full_approval_in_order(flow):
    tid = submitted_tool(flow)
    assert current_step(flow, tid)["position"] == 1
    decide(flow, tid, "u-super-admin", "approved")
    assert get_tool(flow, tid)["status"] == "in_review"
    assert current_step(flow, tid)["position"] == 2
    decide(flow, tid, "u-practice-admin", "approved")
    assert get_tool(flow, tid)["status"] == "approved"
    assert current_step(flow, tid) is None


def test_steps_cannot_be_skipped(flow):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError, match="Step 1"):
        decide(flow, tid, "u-practice-admin", "approved")


@pytest.mark.parametrize("user", ["u-builder", "u-specialist", "u-tool-user", "u-practice-admin"])
def test_wrong_role_cannot_decide_step_one(flow, user):
    # Owned by the super admin, so the refusal is about role, not self-approval.
    tid = submitted_tool(flow, owner="u-super-admin")
    with pytest.raises(ApprovalError, match="must be decided by a super_admin"):
        decide(flow, tid, user, "approved")


def test_rejection_ends_review(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, "u-super-admin", "rejected", "Needs a clearer rationale")
    assert get_tool(flow, tid)["status"] == "rejected"
    with pytest.raises(ApprovalError, match="isn't in review"):
        decide(flow, tid, "u-practice-admin", "approved")


def test_drafts_cannot_be_approved(flow):
    tid = create_tool(flow, name="Draft", template="x", owner_id="u-builder", visibility="firm-wide")
    with pytest.raises(ApprovalError, match="isn't in review"):
        decide(flow, tid, "u-super-admin", "approved")


def test_invalid_decision_word_refused(flow):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError):
        decide(flow, tid, "u-super-admin", "maybe")


# --- no self-approval, admins included ----------------------------------------

def test_builder_cannot_approve_own_tool(conn):
    set_steps(conn, [{"name": "Only step", "approver_role": "builder"}])
    tid = submitted_tool(conn, owner="u-builder")
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(conn, tid, "u-builder", "approved")


def test_super_admin_cannot_approve_own_tool(flow):
    tid = submitted_tool(flow, owner="u-super-admin")
    with pytest.raises(ApprovalError, match="even as an admin"):
        decide(flow, tid, "u-super-admin", "approved")
    assert get_history(flow, tid) == []


def test_practice_admin_cannot_approve_own_tool_at_their_step(flow):
    tid = submitted_tool(flow, owner="u-practice-admin")
    decide(flow, tid, "u-super-admin", "approved")  # step 1 by someone else
    with pytest.raises(ApprovalError, match="even as an admin"):
        decide(flow, tid, "u-practice-admin", "approved")
    assert get_tool(flow, tid)["status"] == "in_review"


def test_admin_cannot_reject_own_tool_either(flow):
    tid = submitted_tool(flow, owner="u-super-admin")
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(flow, tid, "u-super-admin", "rejected")


def test_same_person_cannot_decide_two_steps(conn):
    set_steps(conn, [{"name": "A", "approver_role": "super_admin"},
                     {"name": "B", "approver_role": "super_admin"}])
    tid = submitted_tool(conn)
    decide(conn, tid, "u-super-admin", "approved")
    with pytest.raises(ApprovalError, match="another person"):
        decide(conn, tid, "u-super-admin", "approved")


# --- history ------------------------------------------------------------------

def test_history_records_every_decision_in_order(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, "u-super-admin", "approved", "Looks safe")
    decide(flow, tid, "u-practice-admin", "approved", "Fits our library")
    history = get_history(flow, tid)
    assert [(h["position"], h["approver_id"], h["decision"], h["comment"]) for h in history] == [
        (1, "u-super-admin", "approved", "Looks safe"),
        (2, "u-practice-admin", "approved", "Fits our library"),
    ]
    assert all(h["decided_at"] for h in history)


def test_refused_attempts_leave_no_history(flow):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError):
        decide(flow, tid, "u-tool-user", "approved")
    assert get_history(flow, tid) == []
