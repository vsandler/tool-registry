"""API tests. Each test gets a fresh in-memory app loaded with the made-up seed data."""

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app


@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def as_(persona):
    return {"X-Persona": persona}


def new_tool(client, owner="u-builder", **overrides):
    body = dict(name=f"API tool {owner}", template="Draft a note about {{topic}}.",
                visibility="firm-wide", practice="Tax",
                rationale="One blank keeps it simple to reuse.")
    body.update(overrides)
    r = client.post("/tools", json=body, headers=as_(owner))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert client.post(f"/tools/{tid}/submit", headers=as_(owner)).status_code == 200
    return tid


def decide(client, tid, persona, **body):
    body.setdefault("decision", "approved")
    return client.post(f"/tools/{tid}/decisions", json=body, headers=as_(persona))


def publish(client, tid, area="compliance", specialist="u-specialist", **publish_body):
    publish_body.setdefault("visibility", "firm-wide")
    assert decide(client, tid, "u-super-admin", route_to=area).status_code == 200
    assert decide(client, tid, specialist).status_code == 200
    r = decide(client, tid, "u-super-admin", **publish_body)
    assert r.status_code == 200, r.text
    return r.json()


# --- personas and identity -----------------------------------------------------

def test_personas_list_feeds_the_dropdown(client):
    roles = {p["role"] for p in client.get("/personas").json()}
    assert roles == {"builder", "practice_admin", "super_admin", "specialist_reviewer", "tool_user"}


def test_approval_steps_endpoint_shows_stored_order(client):
    steps = client.get("/approval-steps").json()["steps"]
    assert [s["action"] for s in steps] == ["route", "review", "publish"]


def test_missing_persona_header_refused(client):
    assert client.get("/tools").status_code == 422


def test_unknown_persona_refused(client):
    assert client.get("/tools", headers=as_("u-nobody")).status_code == 401


# --- create, submit, checks ----------------------------------------------------

def test_submit_runs_checks_and_returns_flags(client):
    r = client.post("/tools", headers=as_("u-builder"), json=dict(
        name="Leaky", template="Email {{name}} at casey.sample@example.com",
        visibility="firm-wide", rationale="Testing the client data check."))
    tid = r.json()["id"]
    result = client.post(f"/tools/{tid}/submit", headers=as_("u-builder")).json()
    assert result["flagged"] is True
    assert result["tool"]["status"] == "in_review"  # flagged, not rejected


def test_only_owner_can_submit_via_api(client):
    r = client.post("/tools", headers=as_("u-builder"), json=dict(
        name="Mine", template="x", visibility="firm-wide"))
    tid = r.json()["id"]
    assert client.post(f"/tools/{tid}/submit", headers=as_("u-tool-user")).status_code == 403


def test_bad_visibility_on_create_is_400(client):
    r = client.post("/tools", headers=as_("u-builder"), json=dict(
        name="T", template="x", visibility="secret"))
    assert r.status_code == 400


def test_seeded_failing_submission_visible_with_flags(client):
    queue = client.get("/admin/review-queue", headers=as_("u-super-admin")).json()
    bad = next(t for t in queue if t["name"] == "Client welcome letter")
    assert bad["flagged"] is True
    assert {c["name"] for c in bad["checks"] if not c["passed"]} == {
        "no_client_data", "variables_match", "has_rationale", "practice_set"}


# --- approval flow through the API ------------------------------------------------

def test_full_flow_publishes_and_shows_in_catalogue(client):
    tid = new_tool(client)
    tool = publish(client, tid)
    assert tool["status"] == "published"
    assert [h["detail"] for h in tool["history"]] == [
        "routed to compliance", "", "published as firm-wide"]
    catalogue = client.get("/tools", headers=as_("u-tool-user")).json()
    assert tid in [t["id"] for t in catalogue]


def test_route_without_area_is_400(client):
    tid = new_tool(client)
    assert decide(client, tid, "u-super-admin").status_code == 400


def test_wrong_specialist_area_is_403(client):
    tid = new_tool(client)
    decide(client, tid, "u-super-admin", route_to="marketing")
    assert decide(client, tid, "u-specialist").status_code == 403  # compliance specialist


def test_super_admin_cannot_approve_own_tool_via_api(client):
    tid = new_tool(client, owner="u-super-admin")
    r = decide(client, tid, "u-super-admin", route_to="compliance")
    assert r.status_code == 403
    assert "your own tool" in r.json()["detail"]


def test_practice_admin_cannot_approve_own_tool_via_api(client):
    tid = new_tool(client, owner="u-practice-admin")
    decide(client, tid, "u-super-admin", route_to="compliance")
    decide(client, tid, "u-specialist")
    # Even if a practice admin tried the publish step, it's refused (own tool first).
    r = decide(client, tid, "u-practice-admin", visibility="firm-wide")
    assert r.status_code == 403 and "your own tool" in r.json()["detail"]


def test_decision_on_missing_tool_is_404(client):
    assert decide(client, 9999, "u-super-admin", route_to="compliance").status_code == 404


def test_history_endpoint(client):
    tid = new_tool(client)
    decide(client, tid, "u-super-admin", route_to="technology", comment="AI-heavy tool")
    history = client.get(f"/tools/{tid}/history", headers=as_("u-builder")).json()
    assert history[0]["comment"] == "AI-heavy tool"
    assert history[0]["detail"] == "routed to technology"


# --- visibility in the catalogue --------------------------------------------------

def test_practice_only_tool_hidden_from_other_practices(client):
    tid = new_tool(client)
    publish(client, tid, visibility="practice-only", practice="Tax")
    tax_ids = [t["id"] for t in client.get("/tools", headers=as_("u-builder")).json()]
    audit_ids = [t["id"] for t in client.get("/tools", headers=as_("u-tool-user")).json()]
    assert tid in tax_ids          # builder is in Tax
    assert tid not in audit_ids    # tool user is in Audit


def test_unpublished_tools_not_in_catalogue(client):
    tid = new_tool(client)
    ids = [t["id"] for t in client.get("/tools", headers=as_("u-tool-user")).json()]
    assert tid not in ids


def test_tool_user_cannot_view_unpublished_tool(client):
    tid = new_tool(client)
    assert client.get(f"/tools/{tid}", headers=as_("u-tool-user")).status_code == 403


# --- personalising ------------------------------------------------------------

def test_personalise_published_tool(client):
    tid = new_tool(client)
    publish(client, tid)
    r = client.post(f"/tools/{tid}/personalise", headers=as_("u-tool-user"),
                    json={"values": {"topic": "quarterly planning"}})
    assert r.json()["text"] == "Draft a note about quarterly planning."


def test_personalise_missing_value_is_400(client):
    tid = new_tool(client)
    publish(client, tid)
    r = client.post(f"/tools/{tid}/personalise", headers=as_("u-tool-user"), json={"values": {}})
    assert r.status_code == 400


def test_cannot_personalise_unpublished_tool(client):
    tid = new_tool(client)
    r = client.post(f"/tools/{tid}/personalise", headers=as_("u-tool-user"),
                    json={"values": {"topic": "x"}})
    assert r.status_code == 403


# --- admin route ----------------------------------------------------------------

@pytest.mark.parametrize("admin", ["u-super-admin", "u-practice-admin"])
def test_admin_review_queue_open_to_admins(client, admin):
    queue = client.get("/admin/review-queue", headers=as_(admin)).json()
    assert {t["name"] for t in queue} == {
        "Meeting summary", "Engagement letter draft", "Client welcome letter"}
    assert all(t["current_step"]["action"] == "route" for t in queue)


# Specialist reviewers were removed from this list on purpose: DECISIONS.md #10
# (option A) lets them open the queue, showing only their area's work. That is tested
# in tests/test_api_routing.py.
@pytest.mark.parametrize("persona", ["u-builder", "u-tool-user"])
def test_admin_review_queue_closed_to_non_admins(client, persona):
    assert client.get("/admin/review-queue", headers=as_(persona)).status_code == 403


def test_admin_review_queue_is_read_only(client):
    for method in ("post", "put", "patch", "delete"):
        r = getattr(client, method)("/admin/review-queue", headers=as_("u-super-admin"))
        assert r.status_code == 405, method


def test_review_queue_drops_published_tools(client):
    tid = new_tool(client)
    publish(client, tid)
    queue = client.get("/admin/review-queue", headers=as_("u-super-admin")).json()
    assert tid not in [t["id"] for t in queue]
