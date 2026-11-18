"""'Can I act on this tool, and if not, why?' for the persona viewing it, plus the
submitted date the Review queue sorts by (Phase 9, step 2).

my_action must follow exactly the same rules as decide(): one test checks that every
persona told "you can't" really is refused, and the one told "you can" succeeds.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app
from registry.approvals import (
    MIN_REJECT_COMMENT,
    ApprovalError,
    decide,
    ensure_default_steps,
    my_action,
    set_steps,
)
from registry.db import connect
from registry.personas import PERSONAS
from registry.tools import create_tool, get_tool, submit_tool

SUPER = "u-super-admin"
COMPLIANCE = "u-specialist"
TECH = "u-specialist-tech"
MARKETING = "u-specialist-marketing"
EVERYONE = [p["id"] for p in PERSONAS]

OWN_TOOL = "You built this tool, so you can't approve or reject it."


@pytest.fixture
def flow(conn):
    ensure_default_steps(conn)
    return conn


def submitted_tool(conn, owner="u-builder", name="Action tool"):
    tid = create_tool(conn, name=name, template="Hi {{name}}", owner_id=owner,
                      visibility="firm-wide", rationale="A clear, reusable greeting.")
    submit_tool(conn, tid, owner)
    return tid


def action(conn, tid, user):
    return my_action(conn, tid, user)


# --- who can act at each step, and the plain reason for everyone else ---------------------

def test_super_admin_can_route_and_is_asked_for_areas(flow):
    tid = submitted_tool(flow)
    a = action(flow, tid, SUPER)
    assert a["can_decide"] is True and a["reason"] is None
    assert a["needs"] == "areas"
    assert a["step_position"] == 1


@pytest.mark.parametrize("owner", ["u-builder", SUPER, COMPLIANCE])
def test_owner_is_told_they_built_it(flow, owner):
    tid = submitted_tool(flow, owner=owner)
    if owner == COMPLIANCE:
        decide(flow, tid, SUPER, "approved", route_to="compliance")
    a = action(flow, tid, owner)
    assert a["can_decide"] is False
    assert a["reason"] == OWN_TOOL


@pytest.mark.parametrize("user", [COMPLIANCE, "u-tool-user", "u-practice-admin"])
def test_others_are_told_who_it_is_waiting_for_at_routing(flow, user):
    tid = submitted_tool(flow)
    a = action(flow, tid, user)
    assert a["can_decide"] is False
    assert a["reason"] == "Waiting for the Super admin."


def test_review_steps_say_which_specialist_is_next(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, SUPER, "approved", route_to=["compliance", "marketing"])
    assert action(flow, tid, COMPLIANCE)["can_decide"] is True
    assert action(flow, tid, COMPLIANCE)["needs"] is None
    for user in (MARKETING, TECH, SUPER):
        a = action(flow, tid, user)
        assert a["can_decide"] is False
        assert a["reason"] == "Waiting for a Compliance specialist."
    decide(flow, tid, COMPLIANCE, "approved")
    assert action(flow, tid, MARKETING)["can_decide"] is True
    assert action(flow, tid, COMPLIANCE)["reason"] == "Waiting for a Marketing specialist."


def test_publish_step_asks_the_super_admin_for_visibility(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, SUPER, "approved", route_to="technology")
    decide(flow, tid, TECH, "approved")
    a = action(flow, tid, SUPER)
    assert a["can_decide"] is True and a["needs"] == "visibility"
    assert a["final"] is True


def test_someone_who_decided_another_step_is_told_why(conn):
    set_steps(conn, [
        {"name": "Route", "approver_role": "specialist_reviewer", "action": "route"},
        {"name": "Review", "approver_role": "specialist_reviewer", "action": "review",
         "different_person": True},
    ])
    tid = submitted_tool(conn)
    decide(conn, tid, COMPLIANCE, "approved", route_to="compliance")
    a = action(conn, tid, COMPLIANCE)
    assert a["can_decide"] is False
    assert a["reason"] == ("You've already decided another step of this tool, "
                           "so someone else must decide this one.")


def test_finished_or_unsubmitted_tools_explain_the_review_is_not_open(flow):
    draft = create_tool(flow, name="Draft", template="x", owner_id="u-builder",
                        visibility="firm-wide")
    assert action(flow, draft, SUPER)["reason"] == "This tool hasn't been submitted yet."

    rejected = submitted_tool(flow, name="To reject")
    decide(flow, rejected, SUPER, "rejected", "Duplicates another tool")
    assert action(flow, rejected, SUPER)["reason"] == (
        "This tool was rejected, so the review is over.")

    published = submitted_tool(flow, name="To publish")
    decide(flow, published, SUPER, "approved", route_to="marketing")
    decide(flow, published, MARKETING, "approved")
    decide(flow, published, SUPER, "approved", visibility="firm-wide")
    assert action(flow, published, SUPER)["reason"] == "Published. Nothing left to decide."
    assert action(flow, published, SUPER)["can_decide"] is False


def test_my_action_tells_the_screen_the_reject_comment_rule(flow):
    tid = submitted_tool(flow)
    assert action(flow, tid, SUPER)["reject_comment_min"] == MIN_REJECT_COMMENT == 10


# --- my_action and decide() always agree -------------------------------------------------------

def inputs_for(a):
    if a["needs"] == "areas":
        return {"route_to": ["compliance", "marketing"]}
    if a["needs"] == "visibility":
        return {"visibility": "firm-wide"}
    return {}


@pytest.mark.parametrize("decided_so_far", [0, 1, 2, 3])
def test_my_action_matches_what_decide_allows_for_every_persona(flow, decided_so_far):
    """At each point in a two-specialist review, everyone told "you can't" is
    refused by decide(), and exactly one person is told "you can"."""
    tid = submitted_tool(flow)
    deciders = [(SUPER, {"route_to": ["compliance", "marketing"]}), (COMPLIANCE, {}),
                (MARKETING, {})]
    for user, inputs in deciders[:decided_so_far]:
        decide(flow, tid, user, "approved", **inputs)

    allowed = []
    for user in EVERYONE:
        a = action(flow, tid, user)
        if a["can_decide"]:
            allowed.append(user)
            continue
        with pytest.raises(ApprovalError):
            decide(flow, tid, user, "approved", **inputs_for(action(flow, tid, SUPER)))
    assert len(allowed) == 1
    who = allowed[0]
    decide(flow, tid, who, "approved", **inputs_for(action(flow, tid, who)))


# --- submitted date --------------------------------------------------------------------------

def test_submit_records_when_the_tool_was_submitted(flow):
    draft = create_tool(flow, name="Draft", template="x", owner_id="u-builder",
                        visibility="firm-wide")
    assert get_tool(flow, draft)["submitted_at"] is None
    tid = submitted_tool(flow)
    assert get_tool(flow, tid)["submitted_at"]


def test_older_database_gets_submitted_dates_filled_in(tmp_path):
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL, practice TEXT, specialty TEXT, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE tools (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', template TEXT NOT NULL,
            variables TEXT NOT NULL DEFAULT '[]', visibility TEXT NOT NULL, practice TEXT,
            owner_id TEXT NOT NULL, rationale TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft', routed_to TEXT, created_at TEXT NOT NULL);
        CREATE TABLE check_results (id INTEGER PRIMARY KEY AUTOINCREMENT, tool_id INTEGER NOT NULL,
            check_name TEXT NOT NULL, passed INTEGER NOT NULL, message TEXT NOT NULL,
            checked_at TEXT NOT NULL);
        INSERT INTO users VALUES ('u-builder', 'Avery Quill', 'avery.quill@example.com',
            'builder', 'Tax', NULL, 1);
        INSERT INTO tools (id, name, template, visibility, owner_id, status, created_at)
            VALUES (1, 'Old submitted', 'x', 'firm-wide', 'u-builder', 'in_review',
                    '2026-11-01T09:00:00+00:00'),
                   (2, 'Old draft', 'x', 'firm-wide', 'u-builder', 'draft',
                    '2026-11-01T09:00:00+00:00');
        INSERT INTO check_results (tool_id, check_name, passed, message, checked_at)
            VALUES (1, 'has_rationale', 1, 'ok', '2026-11-02T10:00:00+00:00');
    """)
    old.commit()
    old.close()
    conn = connect(path)
    assert get_tool(conn, 1)["submitted_at"] == "2026-11-02T10:00:00+00:00"
    assert get_tool(conn, 2)["submitted_at"] is None
    conn.close()


# --- through the API ---------------------------------------------------------------------------

@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def test_tool_detail_includes_my_action_for_the_viewer(client):
    tid = client.post("/tools", headers={"X-Persona": "u-builder"}, json=dict(
        name="Viewer tool", template="Hi {{name}}", visibility="firm-wide",
        rationale="A clear, reusable greeting.")).json()["id"]
    client.post(f"/tools/{tid}/submit", headers={"X-Persona": "u-builder"})
    as_super = client.get(f"/tools/{tid}", headers={"X-Persona": SUPER}).json()
    as_owner = client.get(f"/tools/{tid}", headers={"X-Persona": "u-builder"}).json()
    assert as_super["my_action"]["can_decide"] is True
    assert as_owner["my_action"] == {**as_owner["my_action"], "can_decide": False,
                                     "reason": OWN_TOOL}


def test_queue_items_say_whether_they_are_waiting_on_me(client):
    queue = client.get("/admin/review-queue", headers={"X-Persona": SUPER}).json()
    # The three seeded tools are all waiting for the Super admin to route them.
    assert queue and all(t["my_action"]["can_decide"] for t in queue)
    as_practice_admin = client.get("/admin/review-queue",
                                   headers={"X-Persona": "u-practice-admin"}).json()
    assert not any(t["my_action"]["can_decide"] for t in as_practice_admin)


def test_queue_is_oldest_submitted_first(client):
    headers = {"X-Persona": "u-builder"}
    ids = []
    for name in ("Later one", "Even later one"):
        tid = client.post("/tools", headers=headers, json=dict(
            name=name, template="Hi {{name}}", visibility="firm-wide",
            rationale="A clear, reusable greeting.")).json()["id"]
        client.post(f"/tools/{tid}/submit", headers=headers)
        ids.append(tid)
    queue = client.get("/admin/review-queue", headers={"X-Persona": SUPER}).json()
    dates = [t["submitted_at"] for t in queue]
    assert dates == sorted(dates)
    assert [t["id"] for t in queue][-2:] == ids
