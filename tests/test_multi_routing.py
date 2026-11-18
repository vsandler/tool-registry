"""Routing one tool through one or more specialist areas, in order (DECISIONS.md #11).

At step 1 the Super admin picks one or more areas. Each becomes its own review step,
in the order picked, so every tool gets its own list of approval steps:
route -> review (area 1) -> review (area 2) -> ... -> publish.
Tools routed before this change keep working on the shared list.
"""

import pytest

from registry.approvals import (
    ApprovalError,
    current_step,
    decide,
    ensure_default_steps,
    get_history,
    get_progress,
    get_tool_steps,
    set_steps,
)
from registry.tools import create_tool, get_tool, now, submit_tool

SUPER = "u-super-admin"
SUPER_2 = "u-super-admin-2"  # a second, made-up Super admin, added per test below
COMPLIANCE = "u-specialist"
TECH = "u-specialist-tech"
MARKETING = "u-specialist-marketing"


@pytest.fixture
def flow(conn):
    ensure_default_steps(conn)
    return conn


def add_second_super_admin(conn):
    conn.execute(
        "INSERT INTO users (id, name, email, role, practice, specialty) VALUES "
        "(?, 'Rowan Example', 'rowan.example@example.com', 'super_admin', NULL, NULL)",
        (SUPER_2,),
    )
    conn.commit()


def submitted_tool(conn, owner="u-builder", **overrides):
    spec = dict(name=f"Multi tool by {owner}", template="Hi {{name}}", owner_id=owner,
                visibility="firm-wide", practice="Tax", rationale="A clear, reusable greeting.")
    spec.update(overrides)
    tid = create_tool(conn, **spec)
    submit_tool(conn, tid, owner)
    return tid


def route(conn, tid, areas, user=SUPER):
    return decide(conn, tid, user, "approved", route_to=areas)


def shape(steps):
    return [(s["position"], s["action"], s["area"]) for s in steps]


# --- routing to one or more areas ------------------------------------------------------

@pytest.mark.parametrize("route_to", ["compliance", ["compliance"]])
def test_route_to_one_area_still_works_as_before(flow, route_to):
    tid = submitted_tool(flow)
    route(flow, tid, route_to)
    assert shape(get_tool_steps(flow, tid)) == [
        (1, "route", None), (2, "review", "compliance"), (3, "publish", None)]
    decide(flow, tid, COMPLIANCE, "approved")
    decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    assert get_tool(flow, tid)["status"] == "published"


def test_route_to_two_areas_creates_one_review_step_each_in_order(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    assert shape(get_tool_steps(flow, tid)) == [
        (1, "route", None), (2, "review", "compliance"), (3, "review", "marketing"),
        (4, "publish", None)]


def test_route_to_three_areas_keeps_the_chosen_order(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["marketing", "technology", "compliance"])
    reviews = [s["area"] for s in get_tool_steps(flow, tid) if s["action"] == "review"]
    assert reviews == ["marketing", "technology", "compliance"]


@pytest.mark.parametrize("bad, message", [
    ([], "at least one specialist area"),
    (["compliance", "compliance"], "more than once"),
    (["compliance", "legal"], "specialist area"),
    (None, "specialist area"),
])
def test_bad_routing_is_refused_and_leaves_no_trace(flow, bad, message):
    tid = submitted_tool(flow)
    with pytest.raises(ApprovalError, match=message):
        route(flow, tid, bad)
    assert get_history(flow, tid) == []
    assert len(get_tool_steps(flow, tid)) == 3  # still the shared list


def test_steps_before_routing_are_the_shared_list(flow):
    tid = submitted_tool(flow)
    assert shape(get_tool_steps(flow, tid)) == [
        (1, "route", None), (2, "review", None), (3, "publish", None)]


def test_history_records_every_area_in_order(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    assert get_history(flow, tid)[0]["detail"] == "routed to compliance, then marketing"


def test_every_review_step_requires_a_different_person(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing", "technology"])
    reviews = [s for s in get_tool_steps(flow, tid) if s["action"] == "review"]
    assert len(reviews) == 3 and all(s["different_person"] for s in reviews)


# --- reviews happen strictly in order ------------------------------------------------------

def test_two_specialists_in_order_then_publish(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    assert current_step(flow, tid)["area"] == "compliance"
    decide(flow, tid, COMPLIANCE, "approved", "Compliance is fine")
    assert current_step(flow, tid)["area"] == "marketing"
    decide(flow, tid, MARKETING, "approved", "Tone is fine")
    assert current_step(flow, tid)["action"] == "publish"
    decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    assert get_tool(flow, tid)["status"] == "published"
    assert [(h["position"], h["approver_id"]) for h in get_history(flow, tid)] == [
        (1, SUPER), (2, COMPLIANCE), (3, MARKETING), (4, SUPER)]


def test_second_area_cannot_go_first(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    with pytest.raises(ApprovalError, match="compliance review"):
        decide(flow, tid, MARKETING, "approved")
    assert len(get_history(flow, tid)) == 1


def test_specialist_from_an_area_not_chosen_is_refused(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    decide(flow, tid, COMPLIANCE, "approved")
    with pytest.raises(ApprovalError, match="marketing review"):
        decide(flow, tid, TECH, "approved")


def test_first_specialist_cannot_also_do_the_second_review(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    decide(flow, tid, COMPLIANCE, "approved")
    with pytest.raises(ApprovalError):
        decide(flow, tid, COMPLIANCE, "approved")


def test_publish_waits_for_every_review(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    decide(flow, tid, COMPLIANCE, "approved")
    with pytest.raises(ApprovalError, match="specialist_reviewer"):
        decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    assert get_tool(flow, tid)["status"] == "in_review"


# --- a rejection at any review ends the review -----------------------------------------------

@pytest.mark.parametrize("reject_at", [2, 3])
def test_rejection_at_any_review_ends_it(flow, reject_at):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    reviewers = {2: COMPLIANCE, 3: MARKETING}
    for position in range(2, reject_at):
        decide(flow, tid, reviewers[position], "approved")
    decide(flow, tid, reviewers[reject_at], "rejected", "Not suitable")
    assert get_tool(flow, tid)["status"] == "rejected"
    assert current_step(flow, tid) is None
    with pytest.raises(ApprovalError, match="isn't in review"):
        decide(flow, tid, MARKETING, "approved")


# --- no self-approval at any step, for anyone ---------------------------------------------------

def test_owner_cannot_route_own_tool(flow):
    tid = submitted_tool(flow, owner=SUPER)
    with pytest.raises(ApprovalError, match="your own tool"):
        route(flow, tid, ["compliance", "marketing"])


def test_owner_cannot_do_the_first_review_of_own_tool(flow):
    tid = submitted_tool(flow, owner=COMPLIANCE)
    route(flow, tid, ["compliance", "marketing"])
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(flow, tid, COMPLIANCE, "approved")


def test_owner_cannot_do_the_second_review_of_own_tool(flow):
    tid = submitted_tool(flow, owner=MARKETING)
    route(flow, tid, ["compliance", "marketing"])
    decide(flow, tid, COMPLIANCE, "approved")
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(flow, tid, MARKETING, "approved")
    assert current_step(flow, tid)["area"] == "marketing"


def test_owner_cannot_publish_own_tool(flow):
    add_second_super_admin(flow)
    tid = submitted_tool(flow, owner=SUPER)
    route(flow, tid, ["compliance", "technology"], user=SUPER_2)
    decide(flow, tid, COMPLIANCE, "approved")
    decide(flow, tid, TECH, "approved")
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    decide(flow, tid, SUPER_2, "approved", visibility="firm-wide")
    assert get_tool(flow, tid)["status"] == "published"


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_owner_cannot_reject_own_tool_at_a_review_either(flow, decision):
    tid = submitted_tool(flow, owner=TECH)
    route(flow, tid, ["compliance", "technology"])
    decide(flow, tid, COMPLIANCE, "approved")
    with pytest.raises(ApprovalError, match="your own tool"):
        decide(flow, tid, TECH, decision)


# --- progress: every step, done or waiting ----------------------------------------------------

def test_progress_marks_each_step_done_or_waiting_with_who_and_when(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    decide(flow, tid, COMPLIANCE, "approved")
    progress = get_progress(flow, tid)
    assert [p["status"] for p in progress] == ["done", "done", "waiting", "waiting"]
    assert [p["current"] for p in progress] == [False, False, True, False]
    assert progress[0]["decided_by_id"] == SUPER and progress[0]["decided_at"]
    assert progress[1]["decided_by_id"] == COMPLIANCE
    assert progress[2]["decided_by_id"] is None
    assert progress[2]["waiting_for"] == "a Marketing specialist"


def test_progress_flags_the_final_step(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    progress = get_progress(flow, tid)
    assert [p["final"] for p in progress] == [False, False, False, True]


def test_progress_after_rejection_shows_where_it_stopped(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    decide(flow, tid, COMPLIANCE, "rejected", "Needs a risk warning")
    progress = get_progress(flow, tid)
    assert [p["status"] for p in progress] == ["done", "rejected", "not_reached", "not_reached"]
    assert not any(p["current"] for p in progress)


def test_progress_after_publishing_is_all_done(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["marketing"])
    decide(flow, tid, MARKETING, "approved")
    decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    assert [p["status"] for p in get_progress(flow, tid)] == ["done", "done", "done"]


# --- older tools and the shared list keep working ---------------------------------------------

def routed_the_old_way(conn, area="compliance"):
    """A tool routed before this change: one area in routed_to, a route decision in
    the history, and no list of steps of its own."""
    tid = submitted_tool(conn, name=f"Older tool {area}")
    conn.execute("UPDATE tools SET routed_to = ? WHERE id = ?", (area, tid))
    conn.execute(
        "INSERT INTO approvals (tool_id, position, step_name, approver_id, decision, comment, "
        "detail, decided_at) VALUES (?, 1, 'Super admin routes to a specialist', ?, "
        "'approved', '', ?, ?)",
        (tid, SUPER, f"routed to {area}", now()),
    )
    conn.commit()
    return tid


def test_older_tool_still_reviews_and_publishes(flow):
    tid = routed_the_old_way(flow, "marketing")
    with pytest.raises(ApprovalError, match="routed to marketing"):
        decide(flow, tid, COMPLIANCE, "approved")
    decide(flow, tid, MARKETING, "approved")
    decide(flow, tid, SUPER, "approved", visibility="firm-wide")
    assert get_tool(flow, tid)["status"] == "published"


def test_older_tool_steps_show_its_single_area(flow):
    tid = routed_the_old_way(flow, "technology")
    assert shape(get_tool_steps(flow, tid)) == [
        (1, "route", None), (2, "review", "technology"), (3, "publish", None)]


def test_routed_tool_keeps_its_own_steps_if_the_shared_list_changes(flow):
    tid = submitted_tool(flow)
    route(flow, tid, ["compliance", "marketing"])
    set_steps(flow, [{"name": "Only", "approver_role": "super_admin", "action": "publish"}])
    assert len(get_tool_steps(flow, tid)) == 4
    decide(flow, tid, COMPLIANCE, "approved")
    assert current_step(flow, tid)["area"] == "marketing"
