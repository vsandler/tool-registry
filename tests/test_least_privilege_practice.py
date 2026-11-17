"""Least privilege for Practice admins (DECISIONS.md #13).

A tool's practice is its owner's practice. A Practice admin sees only their own
practice's tools in the Review queue and in tool details. The Super admin still sees
everything; owners and the published-tool (catalogue) rules are unchanged.
"""

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app

OTHER_PRACTICE = "This tool belongs to another practice."
TAX_ADMIN = "u-practice-admin"          # Morgan Fennel, Tax
AUDIT_ADMIN = "u-practice-admin-audit"  # made up for these tests, Audit
TAX_BUILDER = "u-builder"               # Avery Quill, Tax
AUDIT_OWNER = "u-tool-user"             # Jamie Larkspur, Audit
NO_PRACTICE_OWNER = "u-specialist"      # Sam Thistle: specialists have no practice


@pytest.fixture
def client():
    app = create_app(":memory:")
    app.state.conn.execute(
        "INSERT INTO users (id, name, email, role, practice, specialty) VALUES "
        "(?, 'Robin Example', 'robin.example@example.com', 'practice_admin', 'Audit', NULL)",
        (AUDIT_ADMIN,),
    )
    app.state.conn.commit()
    with TestClient(app) as c:
        yield c


def as_(persona):
    return {"X-Persona": persona}


def submitted(client, owner, name):
    tid = client.post("/tools", headers=as_(owner), json=dict(
        name=name, template="Hi {{name}}", visibility="firm-wide",
        rationale="A clear, reusable greeting.")).json()["id"]
    r = client.post(f"/tools/{tid}/submit", headers=as_(owner))
    assert r.status_code == 200, r.text
    return tid


def queue_ids(client, persona):
    r = client.get("/admin/review-queue", headers=as_(persona))
    assert r.status_code == 200, r.text
    return {t["id"] for t in r.json()}


def view(client, tid, persona):
    return client.get(f"/tools/{tid}", headers=as_(persona))


# --- own practice allowed ------------------------------------------------------------------

def test_practice_admin_sees_own_practice_tools_in_the_queue(client):
    tax = submitted(client, TAX_BUILDER, "Tax tool")
    audit = submitted(client, AUDIT_OWNER, "Audit tool")
    assert tax in queue_ids(client, TAX_ADMIN)
    assert audit in queue_ids(client, AUDIT_ADMIN)


def test_practice_admin_can_open_own_practice_tool(client):
    tax = submitted(client, TAX_BUILDER, "Tax tool")
    assert view(client, tax, TAX_ADMIN).status_code == 200
    assert client.get(f"/tools/{tax}/history", headers=as_(TAX_ADMIN)).status_code == 200


# --- other practice refused --------------------------------------------------------------------

def test_practice_admin_does_not_see_other_practice_tools_in_the_queue(client):
    tax = submitted(client, TAX_BUILDER, "Tax tool")
    audit = submitted(client, AUDIT_OWNER, "Audit tool")
    assert audit not in queue_ids(client, TAX_ADMIN)
    assert tax not in queue_ids(client, AUDIT_ADMIN)


@pytest.mark.parametrize("admin, owner", [(TAX_ADMIN, AUDIT_OWNER), (AUDIT_ADMIN, TAX_BUILDER)])
def test_practice_admin_is_refused_other_practice_tool_details(client, admin, owner):
    tid = submitted(client, owner, "Someone else's tool")
    r = view(client, tid, admin)
    assert r.status_code == 403
    assert r.json() == {"detail": OTHER_PRACTICE}
    history = client.get(f"/tools/{tid}/history", headers=as_(admin))
    assert history.status_code == 403 and history.json() == {"detail": OTHER_PRACTICE}


def test_tool_whose_owner_has_no_practice_is_not_shown_to_practice_admins(client):
    tid = submitted(client, NO_PRACTICE_OWNER, "Specialist's own tool")
    assert tid not in queue_ids(client, TAX_ADMIN)
    assert view(client, tid, TAX_ADMIN).json() == {"detail": OTHER_PRACTICE}


# --- the Super admin still sees all ---------------------------------------------------------------

def test_super_admin_still_sees_every_practice(client):
    tax = submitted(client, TAX_BUILDER, "Tax tool")
    audit = submitted(client, AUDIT_OWNER, "Audit tool")
    none = submitted(client, NO_PRACTICE_OWNER, "No-practice tool")
    assert {tax, audit, none} <= queue_ids(client, "u-super-admin")
    for tid in (tax, audit, none):
        assert view(client, tid, "u-super-admin").status_code == 200


# --- owners and published-tool rules unchanged ------------------------------------------------------

@pytest.mark.parametrize("owner", [TAX_BUILDER, AUDIT_OWNER, NO_PRACTICE_OWNER])
def test_owners_still_see_their_own_tools(client, owner):
    tid = submitted(client, owner, f"Owned by {owner}")
    assert view(client, tid, owner).status_code == 200


def test_published_firm_wide_tool_from_another_practice_is_visible_like_anyone(client):
    audit = submitted(client, AUDIT_OWNER, "Audit tool")
    for persona, body in (("u-super-admin", {"route_to": ["compliance"]}),
                          ("u-specialist", {}),
                          ("u-super-admin", {"visibility": "firm-wide"})):
        r = client.post(f"/tools/{audit}/decisions", headers=as_(persona),
                        json={"decision": "approved", **body})
        assert r.status_code == 200, r.text
    assert view(client, audit, TAX_ADMIN).status_code == 200


def test_seeded_review_queue_is_unchanged_for_the_tax_practice_admin(client):
    """All three seeded submissions are owned by a Tax builder, so Morgan still sees them."""
    names = {t["name"] for t in client.get("/admin/review-queue", headers=as_(TAX_ADMIN)).json()}
    assert names == {"Meeting summary", "Engagement letter draft", "Client welcome letter"}
