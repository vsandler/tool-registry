"""Fixes for the findings in REVIEW.md (Phase 10). One section per finding."""

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app
from registry.approvals import decide, ensure_default_steps
from registry.personas import practice_names
from registry.tools import InputError, create_tool, get_tool, submit_tool

SUPER = "u-super-admin"
COMPLIANCE = "u-specialist"
RATIONALE = "A clear, reusable greeting for new clients."


@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def persona(user):
    return {"X-Persona": user}


def tool_count(client):
    conn = client.app.state.conn
    return conn.execute("SELECT count(*) FROM tools").fetchone()[0]


NEW_TOOL = dict(name="Review fix tool", description="Made-up test tool.", template="Hi {{name}}",
                visibility="firm-wide", rationale=RATIONALE)


# --- finding 1: only practices from the list are accepted --------------------------------------

PRACTICE_MESSAGE = "Choose a practice from the list: Audit or Tax."


def test_the_practice_list_is_audit_and_tax(client):
    # The made-up firm's practices: the ones people belong to.
    assert practice_names(client.app.state.conn) == ["Audit", "Tax"]


@pytest.mark.parametrize("path", ["/tools", "/submissions"])
def test_an_unknown_practice_is_refused_and_nothing_is_saved(client, path):
    before = tool_count(client)
    r = client.post(path, headers=persona("u-builder"),
                    json={**NEW_TOOL, "visibility": "practice-only", "practice": "Txa"})
    assert r.status_code == 400
    assert r.json()["fields"] == ["practice"]
    assert r.json()["messages"]["practice"] == PRACTICE_MESSAGE
    assert tool_count(client) == before


def test_every_problem_is_still_reported_at_once(client):
    r = client.post("/submissions", headers=persona("u-builder"),
                    json={**NEW_TOOL, "name": "", "visibility": "practice-only",
                          "practice": "Txa"})
    assert r.status_code == 400
    assert set(r.json()["fields"]) == {"name", "practice"}


def test_a_listed_practice_is_accepted_after_tidying(client):
    r = client.post("/submissions", headers=persona("u-builder"),
                    json={**NEW_TOOL, "visibility": "practice-only", "practice": "  Tax "})
    assert r.status_code == 201, r.text
    assert r.json()["tool"]["practice"] == "Tax"


def test_a_blank_practice_is_still_saved_and_flagged_not_refused(client):
    # Unchanged: a practice-only tool with no practice is flagged by the checks.
    r = client.post("/submissions", headers=persona("u-builder"),
                    json={**NEW_TOOL, "visibility": "practice-only", "practice": ""})
    assert r.status_code == 201, r.text
    assert r.json()["flagged"] is True


def test_a_firm_wide_tool_ignores_the_practice_box(client):
    # Unchanged: firm-wide tools store no practice, so whatever was typed doesn't matter.
    r = client.post("/submissions", headers=persona("u-builder"),
                    json={**NEW_TOOL, "practice": "Txa"})
    assert r.status_code == 201, r.text
    assert r.json()["tool"]["practice"] is None


@pytest.fixture
def flow(conn):
    ensure_default_steps(conn)
    return conn


def at_publish_step(conn, **fields):
    tid = create_tool(conn, owner_id="u-builder", **{**NEW_TOOL, **fields})
    submit_tool(conn, tid, "u-builder")
    decide(conn, tid, SUPER, "approved", route_to="compliance")
    decide(conn, tid, COMPLIANCE, "approved")
    return tid


def test_publishing_to_an_unknown_practice_is_refused(flow):
    tid = at_publish_step(flow)
    with pytest.raises(Exception) as refused:
        decide(flow, tid, SUPER, "approved", visibility="practice-only", practice="Txa")
    assert str(refused.value) == PRACTICE_MESSAGE
    tool = get_tool(flow, tid)
    assert tool["status"] == "in_review" and tool["practice"] is None


def test_publishing_to_an_unknown_practice_is_refused_through_the_api(client):
    r = client.post("/submissions", headers=persona("u-builder"), json=NEW_TOOL)
    tid = r.json()["tool"]["id"]
    for user, body in ((SUPER, {"route_to": ["compliance"]}), (COMPLIANCE, {})):
        assert client.post(f"/tools/{tid}/decisions", headers=persona(user),
                           json={"decision": "approved", **body}).status_code == 200
    r = client.post(f"/tools/{tid}/decisions", headers=persona(SUPER),
                    json={"decision": "approved", "visibility": "practice-only",
                          "practice": "Txa"})
    assert r.status_code == 400
    assert r.json()["detail"] == PRACTICE_MESSAGE


def test_publishing_to_a_listed_practice_still_works(flow):
    tid = at_publish_step(flow)
    decide(flow, tid, SUPER, "approved", visibility="practice-only", practice=" Audit ")
    tool = get_tool(flow, tid)
    assert (tool["status"], tool["practice"]) == ("published", "Audit")


def test_create_tool_refuses_an_unknown_practice_directly(conn):
    with pytest.raises(InputError) as refused:
        create_tool(conn, owner_id="u-builder", **{**NEW_TOOL, "visibility": "practice-only",
                                                   "practice": "Txa"})
    assert refused.value.fields == ["practice"]


# --- finding 2: an unknown person can't save or submit a tool ----------------------------------

UNKNOWN_MESSAGE = "Only people in the registry can save or submit tools."


def test_an_unknown_person_cannot_save_a_draft(conn):
    from registry.tools import NotAllowed
    before = conn.execute("SELECT count(*) FROM tools").fetchone()[0]
    with pytest.raises(NotAllowed) as refused:
        create_tool(conn, owner_id="u-nobody", **NEW_TOOL)
    assert str(refused.value) == UNKNOWN_MESSAGE
    assert conn.execute("SELECT count(*) FROM tools").fetchone()[0] == before


def test_an_unknown_person_cannot_submit(conn):
    from registry.tools import NotAllowed
    tid = create_tool(conn, owner_id="u-builder", **NEW_TOOL)
    with pytest.raises(NotAllowed) as refused:
        submit_tool(conn, tid, "u-nobody")
    assert str(refused.value) == UNKNOWN_MESSAGE
    assert get_tool(conn, tid)["status"] == "draft"


def test_the_guard_checks_the_person_before_anything_else(conn, fake_ai):
    # Refused before any check or AI call runs.
    from registry.tools import NotAllowed, create_and_submit
    with pytest.raises(NotAllowed):
        create_and_submit(conn, "u-nobody", **NEW_TOOL)
    assert fake_ai.calls == []


def test_the_api_still_refuses_an_unknown_persona_first(client):
    r = client.post("/submissions", headers=persona("u-nobody"), json=NEW_TOOL)
    assert r.status_code == 401
