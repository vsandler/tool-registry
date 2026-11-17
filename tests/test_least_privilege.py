"""Least privilege for Specialist reviewers (DECISIONS.md #13).

A Specialist can view a tool's details only if its current step is a review for their
area, or they already decided a step of that tool. Otherwise they're refused with a
plain message. Admins still see every tool in review; owners still see their own tools.
"""

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app

REFUSED = "This tool isn't waiting for your area's review."


@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def as_(persona):
    return {"X-Persona": persona}


def submitted(client, name="Least privilege tool"):
    tid = client.post("/tools", headers=as_("u-builder"), json=dict(
        name=name, template="Hi {{name}}", visibility="firm-wide",
        rationale="A clear, reusable greeting.")).json()["id"]
    client.post(f"/tools/{tid}/submit", headers=as_("u-builder"))
    return tid


def decide(client, tid, persona, **body):
    body.setdefault("decision", "approved")
    r = client.post(f"/tools/{tid}/decisions", headers=as_(persona), json=body)
    assert r.status_code == 200, r.text
    return r


def view(client, tid, persona):
    return client.get(f"/tools/{tid}", headers=as_(persona))


# --- the four cases --------------------------------------------------------------------------

def test_own_area_waiting_is_allowed(client):
    tid = submitted(client)
    decide(client, tid, "u-super-admin", route_to=["compliance", "marketing"])
    assert view(client, tid, "u-specialist").status_code == 200


def test_other_area_is_refused_with_the_plain_message(client):
    tid = submitted(client)
    decide(client, tid, "u-super-admin", route_to=["compliance", "marketing"])
    for persona in ("u-specialist-marketing", "u-specialist-tech"):  # marketing comes later
        r = view(client, tid, persona)
        assert r.status_code == 403
        assert r.json() == {"detail": REFUSED}


def test_already_reviewed_is_allowed(client):
    tid = submitted(client)
    decide(client, tid, "u-super-admin", route_to=["compliance", "marketing"])
    decide(client, tid, "u-specialist")  # compliance done; now waiting for marketing
    assert view(client, tid, "u-specialist").status_code == 200
    assert view(client, tid, "u-specialist-marketing").status_code == 200


def test_not_routed_yet_is_refused(client):
    tid = submitted(client)
    for persona in ("u-specialist", "u-specialist-marketing", "u-specialist-tech"):
        r = view(client, tid, persona)
        assert r.status_code == 403
        assert r.json() == {"detail": REFUSED}


# --- the same rule everywhere a tool's details are shown -------------------------------------------

def test_history_follows_the_same_rule(client):
    tid = submitted(client)
    assert client.get(f"/tools/{tid}/history", headers=as_("u-specialist")).status_code == 403
    decide(client, tid, "u-super-admin", route_to=["compliance"])
    assert client.get(f"/tools/{tid}/history", headers=as_("u-specialist")).status_code == 200


def test_specialist_who_rejected_a_tool_can_still_see_it(client):
    tid = submitted(client)
    decide(client, tid, "u-super-admin", route_to=["marketing"])
    decide(client, tid, "u-specialist-marketing", decision="rejected",
           comment="Promises returns in the opening line")
    r = view(client, tid, "u-specialist-marketing")
    assert r.status_code == 200
    assert r.json()["rejection"]["reason"] == "Promises returns in the opening line"
    assert view(client, tid, "u-specialist").json() == {"detail": REFUSED}


# --- what doesn't change -----------------------------------------------------------------------------

@pytest.mark.parametrize("admin", ["u-super-admin", "u-practice-admin"])
def test_admins_still_see_every_tool_in_review(client, admin):
    not_routed = submitted(client, "Not routed")
    routed = submitted(client, "Routed")
    decide(client, routed, "u-super-admin", route_to=["technology"])
    assert view(client, not_routed, admin).status_code == 200
    assert view(client, routed, admin).status_code == 200


def test_owner_still_sees_their_own_tool(client):
    tid = submitted(client)
    assert view(client, tid, "u-builder").status_code == 200


def test_published_firm_wide_tool_is_visible_to_specialists_like_anyone(client):
    tid = submitted(client)
    decide(client, tid, "u-super-admin", route_to=["compliance"])
    decide(client, tid, "u-specialist")
    decide(client, tid, "u-super-admin", visibility="firm-wide")
    assert view(client, tid, "u-specialist-marketing").status_code == 200


def test_queue_and_decisions_are_unaffected(client):
    tid = submitted(client)
    decide(client, tid, "u-super-admin", route_to=["compliance"])
    queue = client.get("/admin/review-queue", headers=as_("u-specialist")).json()
    assert tid in [t["id"] for t in queue]
    assert decide(client, tid, "u-specialist").json()["id"] == tid


def test_other_personas_keep_their_message(client):
    tid = submitted(client)
    r = view(client, tid, "u-tool-user")
    assert r.status_code == 403 and r.json()["detail"] == "You can't view this tool"
