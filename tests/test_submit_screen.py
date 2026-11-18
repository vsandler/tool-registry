"""Phase 9 step 5: the Submit screen (DECISIONS.md #10).

The back end supplies the form's choices, finds the {{blanks}} as the builder types,
refuses unusable input with plain sentences that name the boxes, and labels the rule
flags and AI advice shown after submitting. The screen only asks and displays."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from registry import agent
from registry.api import create_app

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def as_(persona):
    return {"X-Persona": persona}


GOOD = dict(name="Fee summary note", description="Explains fees in plain words.",
            template="Explain the {{service}} fees to {{client_name}} in plain English.",
            visibility="firm-wide", rationale="Fees confuse clients; a fixed structure helps.")


def create(client, persona="u-builder", **overrides):
    return client.post("/tools", headers=as_(persona), json={**GOOD, **overrides})


# --- the form's choices come from the back end -------------------------------------------------

def test_form_choices(client):
    r = client.get("/submit-form", headers=as_("u-builder"))
    assert r.status_code == 200
    form = r.json()
    assert form["visibilities"] == [
        {"value": "firm-wide", "label": "Firm-wide", "asks_practice": False},
        {"value": "practice-only", "label": "Practice-only", "asks_practice": True},
    ]
    assert form["practices"] == ["Audit", "Tax"]   # the practices people belong to
    assert form["default_practice"] == "Tax"       # Avery Quill's own practice
    assert form["rationale_min"] == 20             # the has_rationale check's minimum
    fields = {f["name"]: f for f in form["fields"]}
    assert list(fields) == ["name", "description", "template", "visibility", "practice",
                            "rationale"]
    assert {n for n, f in fields.items() if f["required"]} == {
        "name", "template", "visibility", "rationale"}
    assert fields["rationale"]["label"] == "Why did you build it this way?"
    assert fields["rationale"]["hint"] == (
        "A sentence or two on why you built it this way helps reviewers.")
    assert all(f["label"] and f["hint"] for f in form["fields"])   # every box explained


def test_form_default_practice_is_empty_for_someone_without_one(client):
    form = client.get("/submit-form", headers=as_("u-specialist")).json()
    assert form["default_practice"] is None


def test_form_choices_need_a_persona(client):
    assert client.get("/submit-form").status_code == 422


# --- blanks are found by the back end as the builder types ----------------------------------------

def test_blanks_found_in_order_without_repeats(client):
    r = client.post("/templates/blanks",
                    json={"template": "Hi {{client_name}}, re {{ topic }}. Bye {{client_name}}."})
    assert r.status_code == 200
    assert r.json() == {"blanks": [{"name": "client_name", "label": "Client name"},
                                   {"name": "topic", "label": "Topic"}]}


def test_blanks_for_an_empty_or_plain_template(client):
    assert client.post("/templates/blanks", json={"template": ""}).json() == {"blanks": []}
    assert client.post("/templates/blanks",
                       json={"template": "No blanks {here}"}).json() == {"blanks": []}


def test_blanks_match_what_the_submitted_tool_declares(client):
    """The live list and the saved tool agree, so variables_match passes for a tool
    submitted from the screen."""
    blanks = client.post("/templates/blanks", json={"template": GOOD["template"]}).json()
    tool = create(client).json()
    assert [b["name"] for b in blanks["blanks"]] == tool["variables"]


def test_finding_blanks_saves_nothing(client):
    conn = client.app.state.conn
    before = list(conn.iterdump())
    client.post("/templates/blanks", json={"template": "Dear {{name}} at pat@example.com"})
    assert list(conn.iterdump()) == before


# --- unusable input is refused with plain sentences naming the boxes ------------------------------

NAME_MSG = "Give the tool a name."
TEMPLATE_MSG = "Add the template text."
VISIBILITY_MSG = "Choose who can see the tool: Firm-wide or Practice-only."
RATIONALE_MSG = "Explain why you built it this way."


@pytest.mark.parametrize("overrides, messages", [
    ({"name": ""}, {"name": NAME_MSG}),
    ({"name": "   "}, {"name": NAME_MSG}),
    ({"template": "\n "}, {"template": TEMPLATE_MSG}),
    ({"name": "", "template": ""}, {"name": NAME_MSG, "template": TEMPLATE_MSG}),
    ({"visibility": "secret"}, {"visibility": VISIBILITY_MSG}),
    ({"visibility": ""}, {"visibility": VISIBILITY_MSG}),
])
def test_unusable_input_is_refused_naming_the_boxes(client, overrides, messages):
    r = create(client, **overrides)
    assert r.status_code == 400
    assert r.json() == {"detail": " ".join(messages.values()), "fields": list(messages),
                        "messages": messages}   # one message per box, shown next to it


# --- the rationale is required to submit (DECISIONS.md #15) ---------------------------------

def submit_new(client, persona="u-builder", **overrides):
    return client.post("/submissions", headers=as_(persona), json={**GOOD, **overrides})


@pytest.mark.parametrize("rationale", ["", "   ", "\n\t"])
def test_submitting_with_an_empty_rationale_is_refused(client, rationale):
    r = submit_new(client, rationale=rationale)
    assert r.status_code == 400
    assert r.json() == {"detail": RATIONALE_MSG, "fields": ["rationale"],
                        "messages": {"rationale": RATIONALE_MSG}}


def test_direct_api_submit_of_a_draft_with_no_rationale_is_refused(client):
    """Calling the API directly can't skip the rule: a draft may be saved without a
    rationale, but it can't be sent for review until it has one."""
    r = create(client, rationale="")
    assert r.status_code == 201              # saving a draft is fine
    tid = r.json()["id"]
    r = client.post(f"/tools/{tid}/submit", headers=as_("u-builder"))
    assert r.status_code == 400
    assert r.json() == {"detail": RATIONALE_MSG, "fields": ["rationale"],
                        "messages": {"rationale": RATIONALE_MSG}}
    tool = client.get(f"/tools/{tid}", headers=as_("u-builder")).json()
    assert tool["status"] == "draft" and tool["checks"] == [] and tool["ai_review"] is None


def test_refused_submit_makes_no_ai_call(client, fake_ai):
    tid = create(client, rationale="").json()["id"]
    client.post(f"/tools/{tid}/submit", headers=as_("u-builder"))
    submit_new(client, rationale="")
    assert fake_ai.calls == []


def test_who_may_submit_is_checked_before_the_rationale(client):
    tid = create(client, rationale="").json()["id"]
    assert client.post(f"/tools/{tid}/submit", headers=as_("u-tool-user")).status_code == 403


def test_a_short_rationale_is_accepted_and_flagged(client):
    """Present but too short (like "n/a") isn't refused: the has_rationale check flags it
    for the reviewer, as before."""
    r = submit_new(client, rationale="n/a")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tool"]["status"] == "in_review"
    check = next(c for c in body["checks"] if c["name"] == "has_rationale")
    assert check["passed"] is False


def test_every_problem_is_reported_at_once(client):
    r = submit_new(client, name="", template="", visibility="", rationale="")
    assert r.status_code == 400
    assert r.json()["fields"] == ["name", "template", "visibility", "rationale"]


def test_refused_submission_saves_nothing(client):
    conn = client.app.state.conn
    before = list(conn.iterdump())
    submit_new(client, rationale="")
    submit_new(client, name="")
    assert list(conn.iterdump()) == before


def test_submission_creates_and_submits_in_one_go(client):
    r = submit_new(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tool"]["status"] == "in_review"
    assert body["tool"]["owner_id"] == "u-builder"
    assert body["ai_review"]["advice_only"] is True
    assert body["flagged"] is False


def test_fields_marked_required_are_exactly_the_ones_refused_when_empty(client):
    """The form's "Required" marks come from the back end and must match what it
    actually refuses, box by box."""
    fields = client.get("/submit-form", headers=as_("u-builder")).json()["fields"]
    for i, field in enumerate(fields):
        r = submit_new(client, **{"name": f"Required test {i}", field["name"]: ""})
        refused = r.status_code == 400 and field["name"] in r.json().get("fields", [])
        assert refused == field["required"], (field["name"], r.status_code, r.text)


def test_seeded_sample_submission_keeps_its_empty_rationale(client):
    """The seed's deliberately failing tool stands for a submission made before this
    rule (it's loaded with sample advice, which only the seed can pass), so the demo
    still shows the has_rationale flag."""
    queue = client.get("/admin/review-queue", headers=as_("u-super-admin")).json()
    bad = next(t for t in queue if t["name"] == "Client welcome letter")
    assert bad["rationale"] == ""
    assert not next(c for c in bad["checks"] if c["name"] == "has_rationale")["passed"]


def test_nothing_is_saved_when_refused(client):
    count = client.app.state.conn.execute("SELECT count(*) FROM tools").fetchone()[0]
    create(client, name="")
    assert client.app.state.conn.execute("SELECT count(*) FROM tools").fetchone()[0] == count


def test_flagged_input_is_not_refused(client):
    """Flags don't block submission: a missing rationale or practice is flagged for
    the reviewer, not refused."""
    r = submit_new(client, rationale="n/a", visibility="practice-only", practice="")
    assert r.status_code == 201
    result = r.json()
    assert result["tool"]["status"] == "in_review"
    failed = {c["name"] for c in result["checks"] if not c["passed"]}
    assert {"has_rationale", "practice_set"} <= failed


def test_name_and_practice_are_tidied(client):
    tool = create(client, name="  Fee summary note  ", visibility="practice-only",
                  practice="  Tax ").json()
    assert tool["name"] == "Fee summary note"
    assert tool["practice"] == "Tax"


def test_a_blank_practice_is_stored_as_none(client):
    tool = create(client, visibility="practice-only", practice="  ").json()
    assert tool["practice"] is None


def test_firm_wide_tools_store_no_practice(client):
    """A practice only means something for practice-only tools, so the back end drops
    it for firm-wide ones: the screen doesn't have to know that."""
    tool = create(client, visibility="firm-wide", practice="Tax").json()
    assert tool["practice"] is None


# --- what the builder sees after submitting ------------------------------------------------

def submitted(client, **overrides):
    tid = create(client, **overrides).json()["id"]
    assert client.post(f"/tools/{tid}/submit", headers=as_("u-builder")).status_code == 200
    r = client.get(f"/tools/{tid}", headers=as_("u-builder"))
    assert r.status_code == 200
    return r.json()


def test_every_check_has_a_readable_label(client):
    tool = submitted(client)
    assert {c["name"]: c["label"] for c in tool["checks"]} == {
        "variables_match": "Blanks match",
        "no_client_data": "No client data",
        "has_rationale": "Reason recorded",
        "owner_active": "Owner is current",
        "practice_set": "Practice named",
        "unique_name": "Unique name",
    }


TIPS = {
    "variables_match": "List every blank the template uses, and remove any it doesn't. "
                       "Tools made on the Submit form get this list from the template "
                       "automatically.",
    "no_client_data": "Replace real emails, phone numbers and account numbers with blanks, "
                      "so the stored template holds no client details.",
    "has_rationale": "Write a sentence or two on why the tool is built this way, "
                     "for example why these steps or this wording.",
    "owner_active": "Ask an admin to hand the tool to a current owner.",
    "practice_set": "For a practice-only tool, choose the practice it belongs to.",
    "unique_name": "Look for the existing tool in the Catalog and reuse it, or choose a "
                   "name that says how yours is different.",
}


def test_every_check_has_a_tip_for_next_time(client):
    tool = submitted(client)
    assert {c["name"]: c["tip"] for c in tool["checks"]} == TIPS


def test_flagged_submission_gets_flags_with_tips_and_still_goes_through(client):
    r = submit_new(client, name="Meeting summary", rationale="n/a",
                   template="Email pat.sample@example.com about {{topic}}")
    assert r.status_code == 201
    body = r.json()
    assert body["tool"]["status"] == "in_review" and body["flagged"] is True
    failed = {c["name"]: c for c in body["checks"] if not c["passed"]}
    assert set(failed) == {"has_rationale", "no_client_data", "unique_name"}
    for check in failed.values():
        assert check["label"] and check["message"] and check["tip"] == TIPS[check["name"]]


def test_submit_response_checks_have_labels_too(client):
    tid = create(client).json()["id"]
    result = client.post(f"/tools/{tid}/submit", headers=as_("u-builder")).json()
    assert all(c["label"] for c in result["checks"])


@pytest.mark.parametrize("verdict, summary", [
    ("safe", "The AI found nothing to flag."),
    ("risky", "The AI flagged possible problems. A person decides."),
    ("needs_human", "The AI couldn't give a clear answer, so a person will look closely."),
])
def test_ai_advice_has_a_plain_summary(client, fake_ai, verdict, summary):
    fake_ai.verdict = verdict
    advice = submitted(client)["ai_review"]
    assert advice["summary"] == summary
    assert advice["advice_only"] is True


def test_sample_advice_keeps_its_label_and_gets_a_summary(client):
    queue = client.get("/admin/review-queue", headers=as_("u-super-admin")).json()
    advice = next(t for t in queue if t["name"] == "Meeting summary")["ai_review"]
    assert advice["sample"] is True and advice["label"] == agent.SAMPLE_LABEL
    assert advice["summary"]


def test_builder_sees_who_acts_next(client):
    tool = submitted(client)
    now = [s for s in tool["steps"] if s["current"]]
    assert len(now) == 1 and now[0]["position"] == tool["steps"][0]["position"]
    assert now[0]["waiting_for"]


# --- the screen only asks and displays ------------------------------------------------------

def page():
    return (WEB_DIR / "submit.html").read_text(encoding="utf-8")


def test_submit_page_is_no_longer_a_placeholder():
    assert "coming soon" not in page()


def test_submit_page_gets_its_choices_and_blanks_from_the_back_end():
    code = page()
    assert 'loadOrExplain("/submit-form"' in code
    assert '"/templates/blanks"' in code
    for field in ("visibilities", "asks_practice", "practices", "default_practice",
                  "rationale_min", "blanks", ".label", ".fields", ".required", ".hint"):
        assert field in code, f"the Submit page doesn't use {field}"


def test_submit_page_submits_in_one_call_then_shows_the_back_ends_answer():
    code = page()
    assert 'api("/submissions", { method: "POST"' in code
    assert "/submit`" not in code       # no separate create-then-submit: no stray drafts
    assert "loadOrExplain(`/tools/${" in code


def test_submit_page_shows_flags_and_advice_apart():
    """Flags, advice and the progress line are drawn by the shared pieces in app.js
    (Phase 9, step 6b), so the Submit page and the Review queue show them the same way."""
    code = page()
    assert "Flags don't block submission: a person reviews every tool" in code
    assert "Submitted for review" in code       # the confirmation
    for call in ("renderFlags(tool.checks)", "renderAdvice(tool.ai_review)",
                 "renderProgress(tool.steps"):
        assert call in code, f"the Submit page doesn't use {call}"
    shared = shared_display_code()
    assert "Rule flags" in shared and "AI advice: you decide" in shared
    for field in ("message", "tip", "summary", "issues", "reason", "waiting_for"):
        assert field in shared, f"the shared display code doesn't show {field}"


def shared_display_code():
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    start = js.index("// --- showing a tool's review")
    return js[start:js.index("// ---", start + 10)]


def test_submit_page_does_not_find_blanks_or_check_input_itself():
    code = page()
    assert "{{" not in code and "\\{\\{" not in code and "matchAll(" not in code
    # No browser-side checking: no `required` attribute (it would stop the form before
    # the back end's message could be shown), no length limits. "Required" marks come
    # from the back end's `required` flag.
    assert not re.search(r"required\s*:\s*true|required=|setAttribute\(\s*[\"']required[\"']",
                         code)
    assert not re.search(r"minlength|maxlength", code, re.I)
    assert "err.fields" in code and "err.messages" in code
    # Which visibility needs a practice comes from `asks_practice`, not the page.
    assert "practice-only" not in code and "firm-wide" not in code


def test_submit_page_marks_required_fields_and_explains_the_mark():
    code = page()
    assert "Fields marked * are required." in code
    assert "Required" in code and '"aria-required"' in code


def test_api_helper_passes_on_each_boxs_message():
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    api_helper = js[js.index("export async function api"):]
    api_helper = api_helper[:api_helper.index("\n}\n")]
    assert "error.messages" in api_helper


def test_field_marking_helper_is_shared():
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "export function markInvalid" in js
    helper = js[js.index("export function markInvalid"):]
    helper = helper[:helper.index("\n}\n")]
    assert '"aria-invalid"' in helper and '"aria-describedby"' in helper
    assert "markInvalid(" in page()
    assert "markInvalid(" in (WEB_DIR / "index.html").read_text(encoding="utf-8")
