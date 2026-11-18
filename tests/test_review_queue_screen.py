"""The Review queue screen (Phase 9, step 6).

The screen only asks and displays (DECISIONS.md #12). So the back end gives it:
  - readable "waiting for" text, using the same names as the persona dropdown;
  - the choices each decision needs (areas to route to; visibility and practice to
    publish with, starting from what the builder asked for);
  - `my_action.can_decide`, which must match exactly what a decision would be allowed.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app
from registry.approvals import decide, ensure_default_steps, get_progress, my_action
from registry.personas import PERSONAS, SPECIALIST_AREAS, practice_names
from registry.tools import VISIBILITY_OPTIONS, create_tool, submit_tool

SUPER = "u-super-admin"
COMPLIANCE = "u-specialist"
TECH = "u-specialist-tech"
MARKETING = "u-specialist-marketing"
EVERYONE = [p["id"] for p in PERSONAS]
RATIONALE = "A clear, reusable greeting for new clients."


@pytest.fixture
def flow(conn):
    ensure_default_steps(conn)
    return conn


def submitted_tool(conn, owner="u-builder", name="Queue tool", visibility="firm-wide",
                   practice=None):
    tid = create_tool(conn, name=name, template="Hi {{name}}", owner_id=owner,
                      visibility=visibility, practice=practice, rationale=RATIONALE)
    submit_tool(conn, tid, owner)
    return tid


# --- "waiting for" in plain words -----------------------------------------------------------

def test_waiting_for_uses_the_names_people_see(flow):
    tid = submitted_tool(flow)
    before = get_progress(flow, tid)
    assert before[0]["waiting_for"] == "the Super admin"
    assert before[1]["waiting_for"] == "a specialist (not routed yet)"

    decide(flow, tid, SUPER, "approved", route_to=["technology", "compliance", "marketing"])
    progress = get_progress(flow, tid)
    assert [p["waiting_for"] for p in progress] == [
        None,  # done
        "an AI enablement (technology) specialist",
        "a Compliance specialist",
        "a Marketing specialist",
        "the Super admin",
    ]
    assert my_action(flow, tid, COMPLIANCE)["reason"] == (
        "Waiting for an AI enablement (technology) specialist.")


def test_waiting_for_has_no_raw_codes(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, SUPER, "approved", route_to=list(SPECIALIST_AREAS))
    for step in get_progress(flow, tid):
        text = step["waiting_for"] or ""
        assert "_" not in text
        assert "super admin" not in text  # the label is "Super admin"


# --- the choices each decision needs ----------------------------------------------------------

def test_route_step_offers_every_specialist_area_with_its_label(flow):
    tid = submitted_tool(flow)
    a = my_action(flow, tid, SUPER)
    assert a["needs"] == "areas"
    assert a["choices"] == {"areas": [{"value": k, "label": v}
                                      for k, v in SPECIALIST_AREAS.items()]}


def test_publish_step_offers_visibility_and_practices_starting_from_the_request(flow):
    tid = submitted_tool(flow, visibility="practice-only", practice="Tax")
    decide(flow, tid, SUPER, "approved", route_to="compliance")
    decide(flow, tid, COMPLIANCE, "approved")
    a = my_action(flow, tid, SUPER)
    assert a["needs"] == "visibility"
    assert a["choices"] == {
        "visibilities": VISIBILITY_OPTIONS,
        "practices": practice_names(flow),
        "requested": {"visibility": "practice-only", "practice": "Tax"},
    }
    assert "Tax" in a["choices"]["practices"]


def test_publish_request_for_a_firm_wide_tool_has_no_practice(flow):
    tid = submitted_tool(flow)
    decide(flow, tid, SUPER, "approved", route_to="marketing")
    decide(flow, tid, MARKETING, "approved")
    assert my_action(flow, tid, SUPER)["choices"]["requested"] == {
        "visibility": "firm-wide", "practice": None}


def test_practice_names_are_the_practices_people_belong_to(flow):
    assert practice_names(flow) == sorted({p["practice"] for p in PERSONAS if p["practice"]})


def test_no_choices_where_nothing_needs_choosing(flow):
    tid = submitted_tool(flow)
    for user in EVERYONE:
        if user != SUPER:  # can't decide the route step, so nothing to choose
            assert my_action(flow, tid, user)["choices"] is None
    decide(flow, tid, SUPER, "approved", route_to="compliance")
    review = my_action(flow, tid, COMPLIANCE)
    assert review["can_decide"] is True and review["choices"] is None
    assert my_action(flow, tid, SUPER)["choices"] is None  # waiting for the specialist


# --- through the API, as the screen will use it ----------------------------------------------

@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def persona(user):
    return {"X-Persona": user}


def submit_via_api(client, name="Screen tool", visibility="firm-wide", practice=None):
    r = client.post("/submissions", headers=persona("u-builder"), json=dict(
        name=name, description="Made-up test tool.", template="Hi {{name}}",
        visibility=visibility, practice=practice, rationale=RATIONALE))
    assert r.status_code == 201, r.text
    return r.json()["tool"]["id"]


def approve_with_choices(client, tid, user):
    """Approve the way the screen would: using only the choices the back end gave."""
    a = client.get(f"/tools/{tid}", headers=persona(user)).json()["my_action"]
    body = {"decision": "approved"}
    if a["needs"] == "areas":
        body["route_to"] = [c["value"] for c in a["choices"]["areas"][:2]]
    if a["needs"] == "visibility":
        body.update(a["choices"]["requested"])
    return client.post(f"/tools/{tid}/decisions", headers=persona(user), json=body)


@pytest.mark.parametrize("stage", [0, 1, 2, 3])
@pytest.mark.parametrize("user", EVERYONE)
def test_waiting_on_me_matches_what_a_decision_would_be_allowed(user, stage):
    """For every persona and every tool they can open, at each point in a review:
    "can decide" exactly when approving is accepted. Each case gets a fresh app."""
    with TestClient(create_app(":memory:")) as client:
        tid = submit_via_api(client)
        for decider in [SUPER, TECH, "u-specialist"][:stage]:
            assert approve_with_choices(client, tid, decider).status_code == 200

        queue = client.get("/admin/review-queue", headers=persona(user))
        tools = queue.json() if queue.status_code == 200 else []
        own = client.get(f"/tools/{tid}", headers=persona(user))
        if own.status_code == 200 and tid not in [t["id"] for t in tools]:
            tools.append(own.json())

        for tool in tools:
            can = tool["my_action"]["can_decide"]
            r = approve_with_choices(client, tool["id"], user)
            assert (r.status_code == 200) == can, (tool["name"], r.text)
            if not can:
                assert r.status_code == 403
                assert "_" not in r.json()["detail"], r.json()["detail"]  # no raw codes


def test_walk_through_route_two_areas_review_and_publish(client):
    tid = submit_via_api(client, name="Walk-through tool")
    r = approve_with_choices(client, tid, SUPER)
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["steps"]]
    assert names[1:3] == ["AI enablement (technology) review", "Compliance review"]

    assert approve_with_choices(client, tid, TECH).status_code == 200
    assert approve_with_choices(client, tid, COMPLIANCE).status_code == 200
    publish = client.get(f"/tools/{tid}", headers=persona(SUPER)).json()["my_action"]
    assert publish["final"] is True and publish["needs"] == "visibility"

    r = approve_with_choices(client, tid, SUPER)
    assert r.status_code == 200
    assert r.json()["status"] == "published"
    assert r.json()["visibility"] == "firm-wide"
    queue = client.get("/admin/review-queue", headers=persona(SUPER)).json()
    assert tid not in [t["id"] for t in queue]
    catalog = client.get("/tools", headers=persona("u-tool-user")).json()
    assert tid in [t["id"] for t in catalog]


def test_short_rejection_comment_is_refused_next_to_the_comment_box(client):
    tid = submit_via_api(client, name="Short comment tool")
    r = client.post(f"/tools/{tid}/decisions", headers=persona(SUPER),
                    json={"decision": "rejected", "comment": "no"})
    assert r.status_code == 400
    assert r.json()["field"] == "comment"
    assert "at least 10 characters" in r.json()["detail"]
    detail = client.get(f"/tools/{tid}", headers=persona(SUPER)).json()
    assert detail["status"] == "in_review" and detail["rejection"] is None


def test_rejection_leaves_the_queue_and_carries_the_note(client):
    tid = submit_via_api(client, name="Rejected tool")
    r = client.post(f"/tools/{tid}/decisions", headers=persona(SUPER),
                    json={"decision": "rejected", "comment": "Duplicates the welcome letter."})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert body["rejection"]["reason"] == "Duplicates the welcome letter."
    assert body["rejection"]["by"] == "Riley Ashgrove"
    assert body["my_action"]["can_decide"] is False
    queue = client.get("/admin/review-queue", headers=persona(SUPER)).json()
    assert tid not in [t["id"] for t in queue]


# --- shared display pieces in app.js (6b) ------------------------------------------------------

WEB = Path(__file__).resolve().parent.parent / "web"


def shared_function(name):
    js = (WEB / "app.js").read_text(encoding="utf-8")
    marker = f"export function {name}("
    assert marker in js, f"app.js has no shared {name}()"
    body = js[js.index(marker):]
    return body[:body.index("\n}\n")]


def test_rule_flags_are_drawn_once_for_every_screen():
    code = shared_function("renderFlags")
    assert '"Rule flags"' in code
    assert "Facts from the fixed checks, not opinions." in code
    assert "c.passed" in code and "c.label" in code and "c.message" in code
    assert "Next time: " in code and "c.tip" in code
    assert "None: every rule-based check passed." in code


def test_ai_advice_is_drawn_once_and_kept_apart_from_the_flags():
    code = shared_function("renderAdvice")
    assert '"AI advice: you decide"' in code
    assert "Advice only: it never approves or rejects a tool." in code
    for field in ("label", "summary", "issues", "reason"):
        assert f"advice.{field}" in code
    assert "No AI advice for this tool." in code
    assert "checks" not in code  # flags and advice stay separate


def test_progress_line_shows_every_step_from_the_back_end():
    code = shared_function("renderProgress")
    for field in ("status", "current", "decided_by", "decided_at", "waiting_for", "comment"):
        assert f"s.{field}" in code, f"the progress line doesn't show {field}"
    # The final-approval note appears only when the back end says this persona can
    # decide the final step: the page doesn't work out which step is last.
    assert "This is the final approval. Approving publishes the tool." in code
    assert "myAction.final" in code and "myAction.can_decide" in code
    assert "steps.length" not in code and "at(-1)" not in code


def test_shared_display_pieces_draw_text_only():
    for name in ("renderFlags", "renderAdvice", "renderProgress"):
        code = shared_function(name)
        assert "innerHTML" not in code and "insertAdjacentHTML" not in code


# --- the list (6c) -----------------------------------------------------------------------------

def queue_page():
    return (WEB / "queue.html").read_text(encoding="utf-8")


def test_tool_details_name_the_builder(client):
    tid = submit_via_api(client, name="Named builder tool")
    detail = client.get(f"/tools/{tid}", headers=persona(SUPER)).json()
    assert detail["owner_name"] == "Avery Quill"
    queue = client.get("/admin/review-queue", headers=persona(SUPER)).json()
    assert all(t["owner_name"] for t in queue)


def test_queue_page_is_no_longer_a_placeholder():
    code = queue_page()
    assert "coming soon" not in code
    assert "step 6" not in code


def test_queue_page_has_both_views_and_explains_an_empty_one():
    code = queue_page()
    for text in ("Waiting on me", "All in review", "Nothing is waiting on you.",
                 "Show all in review", "Nothing is in review right now."):
        assert text in code, f"the queue page doesn't say {text!r}"


def test_waiting_on_me_comes_from_the_back_end():
    code = queue_page()
    # Which tools wait on this persona is the back end's answer, not a rule here.
    assert "my_action.can_decide" in code
    for forbidden in ("approver_role", "specialty", "owner_id", "routed_to"):
        assert forbidden not in code, f"the queue page reads {forbidden} itself"


def test_queue_rows_show_what_the_back_end_sends_in_its_order():
    code = queue_page()
    for field in ("owner_name", "submitted_at", "step_name", "a.reason"):
        assert field in code, f"the queue rows don't show {field}"
    assert ".sort(" not in code  # oldest first is the back end's order
