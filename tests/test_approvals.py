"""Approval rules for the fixed three-step flow (DECISIONS.md #1):
route (Super admin) -> specialist review -> publish (Super admin)."""

import pytest

from registry.approvals import (
    DEFAULT_APPROVAL_STEPS,
    ApprovalError,
    current_step,
    decide,
    ensure_default_steps,
    get_history,
    get_steps,
    set_steps,
)
from registry.tools import create_tool, get_tool, submit_tool

SUPER = "u-super-admin"
COMPLIANCE = "u-specialist"
TECH = "u-specialist-tech"
MARKETING = "u-specialist-marketing"


@pytest.fixture
def flow(conn):
    ensure_default_steps(conn)
    return conn


def submitted_tool(conn, owner="u-builder", **overrides):
    spec = dict(name=f"Tool by {owner}", template="Hi {{name}}", owner_id=owner,
                visibility="firm-wide", practice="Tax", rationale="A clear, reusable greeting.")
    spec.update(overrides)
    tid = create_tool(conn, **spec)
    submit_tool(conn, tid, owner)
    return tid


def route(conn, tid, area="compliance", user=SUPER):
    return decide(conn, tid, user, "approved", route_to=area)


# --- the order is stored as a list of steps ----------------------------------

def test_default_order_is_stored_as_ordered_list(flow):
    assert [(s["position"], s["approver_role"], s["action"]) for s in get_steps(flow)] == [
        (1, "super_admin", "route"),
        (2, "specialist_reviewer", "review"),
        (3, "super_admin", "publish"),
    ]


def test_ensure_default_steps_does_not_overwrite_an_existing_order(conn):
    custom = [{"name": "Only", "approver_role": "super_admin", "action": "publish"}]
    set_steps(conn, custom)
    ensure_default_steps(conn)
    assert len(get_steps(conn)) == 1


def test_order_rejects_unknown_role_or_action(conn):
    with pytest.raises(ApprovalError):
        set_steps(conn, [{"name": "X", "approver_role": "wizard", "action": "route"}])
    with pytest.raises(ApprovalError):
        set_steps(conn, [{"name": "X", "approver_role": "super_admin", "action": "dance"}])


def test_order_rejects_empty_list(conn):
    with pytest.raises(ApprovalError):
        set_steps(conn, [])


def test_no_order_set_up_is_refused(conn):
    tid = submitted_tool(conn)
    with pytest.raises(ApprovalError, match="No approval order"):
        decide(conn, tid, SUPER, "approved", route_to="compliance")


# --- full happy path -------------------------------------------------------------

def test_full_flow_route_review_publish(flow):
    tid = submitted_tool(flow)
    assert current_step(flow, tid)["action"] == "route"
    route(flow, tid, "compliance")
    assert current_step(flow, tid)["action"] == "review"
    decide(flow, tid, COMPLIANCE, "approved", "No compliance issues")
    assert current_step(flow, tid)["action"] == "publish"
    assert get_tool(flow, tid)["status"] == "in_review"
    decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    assert get_tool(flow, tid)["status"] == "published"
    assert current_step(flow, tid) is None


# --- step 1: routing -----------------------------------------------------------

@pytest.mark.parametrize("area, specialist", [
    ("technology", TECH), ("compliance", COMPLIANCE), ("marketing", MARKETING)])
def test_routing_sends_tool_to_chosen_area(flow, area, specialist):
    tid = submitted_tool(flow)
    tool = route(flow, tid, area)
    assert tool["routed_to"] == area
    decide(flow, tid, specialist, "approved")
    assert current_step(flow, tid)["action"] == "publish"


@pytest.mark.parametrize("bad_area", [None, "", "legal"])
def test_routing_needs_a_valid_specialist_area(flow, bad_area):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError, match="specialist area"):
        decide(flow, tid, SUPER, "approved", route_to=bad_area)
    assert get_history(flow, tid) == []


@pytest.mark.parametrize("user", ["u-practice-admin", COMPLIANCE, "u-tool-user", "u-builder"])
def test_only_super_admin_can_route(flow, user):
    # Owned by someone not in the list, so the refusal is about role, not self-approval.
    tid = submitted_tool(flow, owner=MARKETING)
    with pytest.raises(ApprovalError, match="must be decided by the Super admin, not a "):
        decide(flow, tid, user, "approved", route_to="compliance")


def test_specialist_cannot_skip_ahead_before_routing(flow):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError, match="Step 1"):
        decide(flow, tid, COMPLIANCE, "approved")


# --- step 2: specialist review --------------------------------------------------

@pytest.mark.parametrize("wrong", [TECH, MARKETING])
def test_only_specialist_from_routed_area_can_review(flow, wrong):
    tid = submitted_tool(flow)
    route(flow, tid, "compliance")
    with pytest.raises(ApprovalError, match=r"Compliance review \(this tool was routed to Compliance\)"):
        decide(flow, tid, wrong, "approved")


def test_super_admin_cannot_do_the_specialist_step(flow):
    tid = submitted_tool(flow)
    route(flow, tid, "compliance")
    with pytest.raises(ApprovalError, match="must be decided by a Specialist reviewer"):
        decide(flow, tid, SUPER, "approved")


def test_specialist_must_be_a_different_person(conn):
    # A custom order where one specialist could otherwise decide both steps.
    set_steps(conn, [
        {"name": "Route", "approver_role": "specialist_reviewer", "action": "route"},
        {"name": "Review", "approver_role": "specialist_reviewer", "action": "review",
         "different_person": True},
    ])
    tid = submitted_tool(conn)
    decide(conn, tid, COMPLIANCE, "approved", route_to="compliance")
    with pytest.raises(ApprovalError, match="hasn't decided another step"):
        decide(conn, tid, COMPLIANCE, "approved")


def test_default_review_step_requires_a_different_person(flow):
    review = [s for s in get_steps(flow) if s["action"] == "review"][0]
    assert review["different_person"] is True


# --- step 3: return to Super admin, set visibility, publish ---------------------

def test_tool_returns_to_super_admin_after_specialist(flow):
    tid = submitted_tool(flow)
    route(flow, tid, "marketing")
    decide(flow, tid, MARKETING, "approved")
    step = current_step(flow, tid)
    assert step["approver_role"] == "super_admin" and step["action"] == "publish"
    with pytest.raises(ApprovalError, match="must be decided by the Super admin, not a "):
        decide(flow, tid, MARKETING, "approved", visibility="firm-wide")


def test_same_super_admin_may_route_and_publish(flow):
    tid = submitted_tool(flow)
    route(flow, tid, "technology")
    decide(flow, tid, TECH, "approved")
    decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    assert get_tool(flow, tid)["status"] == "published"
    assert [h["approver_id"] for h in get_history(flow, tid)] == [SUPER, TECH, SUPER]


def test_publish_sets_firm_wide(flow):
    tid = submitted_tool(flow, visibility="practice-only")
    route(flow, tid)
    decide(flow, tid, COMPLIANCE, "approved")
    tool = decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    assert tool["visibility"] == "firm-wide"


def test_publish_sets_practice_only_with_practice(flow):
    tid = submitted_tool(flow, practice=None)
    route(flow, tid)
    decide(flow, tid, COMPLIANCE, "approved")
    tool = decide(flow, tid, SUPER, "approved", visibility="practice-only", practice="Audit")
    assert tool["visibility"] == "practice-only" and tool["practice"] == "Audit"


def test_publish_practice_only_needs_a_practice(flow):
    tid = submitted_tool(flow, practice=None)
    route(flow, tid)
    decide(flow, tid, COMPLIANCE, "approved")
    with pytest.raises(ApprovalError, match="Name the practice"):
        decide(flow, tid, SUPER, "approved", visibility="practice-only")
    assert get_tool(flow, tid)["status"] == "in_review"


@pytest.mark.parametrize("bad", [None, "secret"])
def test_publish_needs_a_valid_visibility(flow, bad):
    tid = submitted_tool(flow)
    route(flow, tid)
    decide(flow, tid, COMPLIANCE, "approved")
    with pytest.raises(ApprovalError, match="Set visibility"):
        decide(flow, tid, SUPER, "approved", visibility=bad)
    assert get_tool(flow, tid)["status"] == "in_review"


# --- rejection, drafts, bad input ---------------------------------------------------

@pytest.mark.parametrize("reject_at", [1, 2, 3])
def test_rejection_at_any_step_is_final(flow, reject_at):
    tid = submitted_tool(flow)
    deciders = [SUPER, COMPLIANCE, SUPER]
    for position in range(1, reject_at):
        kwargs = {"route_to": "compliance"} if position == 1 else {}
        decide(flow, tid, deciders[position - 1], "approved", **kwargs)
    decide(flow, tid, deciders[reject_at - 1], "rejected", "Not reusable enough")
    assert get_tool(flow, tid)["status"] == "rejected"
    with pytest.raises(ApprovalError, match="isn't in review"):
        decide(flow, tid, SUPER, "approved", visibility="firm-wide")


def test_drafts_cannot_be_approved(flow):
    tid = create_tool(flow, name="Draft", template="x", owner_id="u-builder", visibility="firm-wide")
    with pytest.raises(ApprovalError, match="isn't in review"):
        decide(flow, tid, SUPER, "approved", route_to="compliance")


def test_invalid_decision_word_refused(flow):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError):
        decide(flow, tid, SUPER, "maybe")


# --- no self-approval, admins included ----------------------------------------------

def test_super_admin_cannot_route_own_tool(flow):
    tid = submitted_tool(flow, owner=SUPER)
    with pytest.raises(ApprovalError, match="even as an admin"):
        route(flow, tid)
    assert get_history(flow, tid) == []


def test_super_admin_cannot_reject_own_tool(flow):
    tid = submitted_tool(flow, owner=SUPER)
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(flow, tid, SUPER, "rejected")


def test_specialist_cannot_approve_own_tool_routed_to_them(flow):
    tid = submitted_tool(flow, owner=COMPLIANCE)
    route(flow, tid, "compliance")
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(flow, tid, COMPLIANCE, "approved")
    assert get_tool(flow, tid)["status"] == "in_review"


def test_practice_admin_tool_still_cannot_be_self_approved(flow):
    tid = submitted_tool(flow, owner="u-practice-admin")
    with pytest.raises(ApprovalError, match="even as an admin"):
        decide(flow, tid, "u-practice-admin", "approved", route_to="compliance")


def test_builder_cannot_approve_own_tool(conn):
    set_steps(conn, [{"name": "Only", "approver_role": "builder", "action": "publish"}])
    tid = submitted_tool(conn, owner="u-builder")
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(conn, tid, "u-builder", "approved", visibility="firm-wide")


# --- history ------------------------------------------------------------------

def test_history_records_every_decision_in_order(flow):
    tid = submitted_tool(flow)
    route(flow, tid, "compliance")
    decide(flow, tid, COMPLIANCE, "approved", "No issues")
    decide(flow, tid, SUPER, "approved", "Useful for everyone", visibility="firm-wide")
    history = get_history(flow, tid)
    assert [(h["position"], h["approver_id"], h["decision"], h["detail"]) for h in history] == [
        (1, SUPER, "approved", "routed to compliance"),
        (2, COMPLIANCE, "approved", ""),
        (3, SUPER, "approved", "published as firm-wide"),
    ]
    assert history[1]["comment"] == "No issues"
    assert all(h["decided_at"] for h in history)


def test_refused_attempts_leave_no_history(flow):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError):
        decide(flow, tid, "u-tool-user", "approved")
    assert get_history(flow, tid) == []


def test_default_steps_constant_matches_decisions_md():
    assert [s["action"] for s in DEFAULT_APPROVAL_STEPS] == ["route", "review", "publish"]
