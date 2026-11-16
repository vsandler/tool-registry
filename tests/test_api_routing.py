"""API side of multi-specialist routing and the Review queue for Specialists
(DECISIONS.md #10 option A and #11)."""

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app


@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def as_(persona):
    return {"X-Persona": persona}


def new_tool(client, owner="u-builder", name="Routing tool"):
    r = client.post("/tools", headers=as_(owner), json=dict(
        name=name, template="Draft a note about {{topic}}.", visibility="firm-wide",
        rationale="One blank keeps it simple to reuse."))
    tid = r.json()["id"]
    assert client.post(f"/tools/{tid}/submit", headers=as_(owner)).status_code == 200
    return tid


def decide(client, tid, persona, **body):
    body.setdefault("decision", "approved")
    return client.post(f"/tools/{tid}/decisions", json=body, headers=as_(persona))


def queue_ids(client, persona):
    r = client.get("/admin/review-queue", headers=as_(persona))
    assert r.status_code == 200, r.text
    return [t["id"] for t in r.json()]


# --- routing through the API -----------------------------------------------------------

def test_route_to_a_list_of_areas(client):
    tid = new_tool(client)
    r = decide(client, tid, "u-super-admin", route_to=["compliance", "marketing"])
    assert r.status_code == 200, r.text
    assert [s["area"] for s in r.json()["steps"] if s["action"] == "review"] == [
        "compliance", "marketing"]


def test_route_to_a_single_area_as_text_still_works(client):
    tid = new_tool(client)
    assert decide(client, tid, "u-super-admin", route_to="technology").status_code == 200


@pytest.mark.parametrize("bad", [[], ["compliance", "compliance"], ["legal"]])
def test_bad_routing_is_400(client, bad):
    tid = new_tool(client)
    assert decide(client, tid, "u-super-admin", route_to=bad).status_code == 400


def test_full_two_specialist_flow_through_the_api(client):
    tid = new_tool(client)
    decide(client, tid, "u-super-admin", route_to=["compliance", "marketing"])
    assert decide(client, tid, "u-specialist-marketing").status_code == 403  # not its turn
    assert decide(client, tid, "u-specialist").status_code == 200
    assert decide(client, tid, "u-specialist-marketing").status_code == 200
    r = decide(client, tid, "u-super-admin", visibility="firm-wide")
    assert r.json()["status"] == "published"


# --- progress data for the progress line -----------------------------------------------------

def test_tool_detail_includes_progress_for_every_step(client):
    tid = new_tool(client)
    decide(client, tid, "u-super-admin", route_to=["compliance", "marketing"])
    decide(client, tid, "u-specialist")
    steps = client.get(f"/tools/{tid}", headers=as_("u-super-admin")).json()["steps"]
    assert [s["status"] for s in steps] == ["done", "done", "waiting", "waiting"]
    assert steps[1]["decided_by"] == "Sam Thistle"
    assert steps[2]["current"] is True
    assert steps[3]["final"] is True


# --- option A: Specialists open the queue, but see only their area's work ---------------------

def test_specialist_sees_only_tools_waiting_for_their_area(client):
    first_compliance = new_tool(client, name="Compliance first")
    first_marketing = new_tool(client, name="Marketing first")
    not_routed = new_tool(client, name="Not routed yet")
    decide(client, first_compliance, "u-super-admin", route_to=["compliance", "marketing"])
    decide(client, first_marketing, "u-super-admin", route_to=["marketing"])

    assert queue_ids(client, "u-specialist") == [first_compliance]
    assert queue_ids(client, "u-specialist-marketing") == [first_marketing]
    assert queue_ids(client, "u-specialist-tech") == []

    decide(client, first_compliance, "u-specialist")  # now waiting for marketing
    assert queue_ids(client, "u-specialist") == []
    assert set(queue_ids(client, "u-specialist-marketing")) == {first_compliance, first_marketing}
    assert not_routed not in queue_ids(client, "u-specialist-marketing")


@pytest.mark.parametrize("admin", ["u-super-admin", "u-practice-admin"])
def test_admins_still_see_every_tool_in_review(client, admin):
    tid = new_tool(client)
    decide(client, tid, "u-super-admin", route_to=["marketing"])
    names = {t["name"] for t in client.get("/admin/review-queue", headers=as_(admin)).json()}
    assert {"Routing tool", "Meeting summary", "Client welcome letter"} <= names


def test_review_queue_is_the_only_admin_route():
    """Guard: the Review queue is the only /admin route, and the only one that lets
    Specialist reviewers in. A new /admin route must stay admins-only."""
    app = create_app(":memory:")
    admin_routes = sorted(r.path for r in app.routes if r.path.startswith("/admin"))
    assert admin_routes == ["/admin/review-queue"], (
        "A new /admin route was added. Make it admins-only (Practice admin and Super admin; "
        "don't reuse the Review queue's queue_viewer check, which lets Specialist reviewers "
        "in) and add a test that a Specialist reviewer gets 403 on it. Then add it to this "
        f"list. Found: {admin_routes}"
    )


def test_queue_is_still_read_only_for_specialists(client):
    for method in ("post", "put", "patch", "delete"):
        r = getattr(client, method)("/admin/review-queue", headers=as_("u-specialist"))
        assert r.status_code == 405, method
