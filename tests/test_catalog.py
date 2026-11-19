"""Phase 9 step 4: the Catalog screen.

The back end decides everything the Catalog shows and every personalising rule:
which published tools a persona sees, each tool's blanks and their labels, the
owner's name, the visibility label, which values are acceptable, and the download's
file name. The screen only asks and displays (DECISIONS.md #12)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app
from registry.personas import PERSONAS, ROLES

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

MISSING_MESSAGE = "Fill in every blank before downloading your copy: {}."
UNKNOWN_MESSAGE = "This tool has no blank called: {}."


@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def as_(persona):
    return {"X-Persona": persona}


def decide(client, tid, persona, **body):
    body.setdefault("decision", "approved")
    r = client.post(f"/tools/{tid}/decisions", json=body, headers=as_(persona))
    assert r.status_code == 200, r.text


def published_tool(client, owner="u-builder", visibility="firm-wide", practice=None, **overrides):
    """Create, submit and publish a made-up tool; return its id."""
    body = dict(name="Quarterly check-in note",
                description="A short note to open a quarterly check-in.",
                template="Write a note to {{client_name}} about {{topic}}. "
                         "Sign off from {{client_name}}'s adviser.",
                visibility="firm-wide",
                rationale="The client name is a blank so the template never holds client details.")
    body.update(overrides)
    r = client.post("/tools", json=body, headers=as_(owner))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert client.post(f"/tools/{tid}/submit", headers=as_(owner)).status_code == 200
    decide(client, tid, "u-super-admin", route_to="compliance")
    decide(client, tid, "u-specialist")
    decide(client, tid, "u-super-admin", visibility=visibility, practice=practice)
    return tid


def catalogue(client, persona):
    r = client.get("/tools", headers=as_(persona))
    assert r.status_code == 200, r.text
    return r.json()


def entry(client, persona, tid):
    return next(t for t in catalogue(client, persona) if t["id"] == tid)


def personalise(client, tid, values, persona="u-tool-user"):
    return client.post(f"/tools/{tid}/personalize", headers=as_(persona), json={"values": values})


# --- what each catalogue entry carries ---------------------------------------------------

def test_entry_has_owner_name_visibility_label_and_rationale(client):
    tid = published_tool(client)
    tool = entry(client, "u-tool-user", tid)
    assert tool["owner_name"] == "Avery Quill"
    assert tool["visibility_label"] == "Firm-wide"
    assert tool["rationale"] == (
        "The client name is a blank so the template never holds client details.")
    assert tool["description"] == "A short note to open a quarterly check-in."
    assert "{{client_name}}" in tool["template"]


def test_practice_only_label_names_the_practice(client):
    tid = published_tool(client, visibility="practice-only", practice="Tax")
    assert entry(client, "u-builder", tid)["visibility_label"] == "Practice-only: Tax"


def test_blanks_come_from_the_template_in_order_without_repeats(client):
    tid = published_tool(client)
    assert entry(client, "u-tool-user", tid)["blanks"] == [
        {"name": "client_name", "label": "Client name"},
        {"name": "topic", "label": "Topic"},
    ]


def test_blanks_include_ones_the_builder_forgot_to_declare(client):
    """The template is the truth: personalising fills what the template uses, so the
    screen must ask for exactly those, even if the declared list was wrong."""
    tid = published_tool(client, variables=["client_name"])
    names = [b["name"] for b in entry(client, "u-tool-user", tid)["blanks"]]
    assert names == ["client_name", "topic"]


def test_entry_hides_review_internals(client):
    """The catalogue is for reusing tools: rule flags, AI advice and reviewers'
    comments stay in the Review queue and tool details."""
    tid = published_tool(client)
    tool = entry(client, "u-tool-user", tid)
    for internal in ("checks", "flagged", "ai_review", "history", "steps", "rejection"):
        assert internal not in tool


# --- who sees what ---------------------------------------------------------------------

def test_only_published_tools_are_listed(client):
    """The seed data has tools in review and drafts but none published."""
    assert catalogue(client, "u-super-admin") == []


@pytest.mark.parametrize("persona", [p["id"] for p in PERSONAS])
def test_firm_wide_tool_is_seen_by_everyone(client, persona):
    tid = published_tool(client)
    assert tid in [t["id"] for t in catalogue(client, persona)]


@pytest.mark.parametrize("persona, sees", [
    ("u-builder", True),             # Tax
    ("u-practice-admin", True),      # Tax
    ("u-super-admin", True),
    ("u-tool-user", False),          # Audit
    ("u-specialist", False),         # no practice
    ("u-specialist-tech", False),
    ("u-specialist-marketing", False),
])
def test_practice_only_tool_is_seen_by_that_practice_and_the_super_admin(client, persona, sees):
    tid = published_tool(client, visibility="practice-only", practice="Tax")
    assert (tid in [t["id"] for t in catalogue(client, persona)]) is sees


# --- personalising and downloading ----------------------------------------------------------

def test_personalise_fills_every_blank_and_names_the_file(client):
    tid = published_tool(client)
    r = personalise(client, tid, {"client_name": "Pat Example", "topic": "savings goals"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == ("Write a note to Pat Example about savings goals. "
                            "Sign off from Pat Example's adviser.")
    assert body["filename"] == "quarterly-check-in-note.txt"


def test_file_name_never_contains_the_values_typed_in(client):
    """A file name gets seen in download folders and email attachments, so it comes
    from the tool's name only, never from client details."""
    tid = published_tool(client)
    body = personalise(client, tid, {"client_name": "Pat Example", "topic": "x"}).json()
    assert "pat" not in body["filename"].lower()


def test_file_name_is_safe_for_odd_tool_names(client):
    tid = published_tool(client, name="  Fees / Charges: Q&A ✨  ")
    body = personalise(client, tid, {"client_name": "A", "topic": "B"}).json()
    assert body["filename"] == "fees-charges-q-a.txt"


def test_file_name_falls_back_when_the_name_has_no_letters(client):
    tid = published_tool(client, name="✨✨")
    body = personalise(client, tid, {"client_name": "A", "topic": "B"}).json()
    assert body["filename"] == "personalized-tool.txt"


def test_values_that_look_like_blanks_are_not_filled_again(client):
    tid = published_tool(client)
    body = personalise(client, tid, {"client_name": "{{topic}}", "topic": "fees"}).json()
    assert body["text"].startswith("Write a note to {{topic}} about fees.")


@pytest.mark.parametrize("values, missing", [
    ({}, ["client_name", "topic"]),
    ({"client_name": "Pat Example"}, ["topic"]),
    ({"client_name": "", "topic": "fees"}, ["client_name"]),
    ({"client_name": "   ", "topic": "\n\t"}, ["client_name", "topic"]),
])
def test_missing_or_blank_values_are_refused_naming_each_box(client, values, missing):
    tid = published_tool(client)
    r = personalise(client, tid, values)
    assert r.status_code == 400
    labels = {"client_name": "Client name", "topic": "Topic"}
    assert r.json() == {
        "detail": MISSING_MESSAGE.format(", ".join(labels[m] for m in missing)),
        "fields": missing,   # so the screen shows the message next to those boxes
    }


def test_values_for_blanks_the_tool_does_not_have_are_refused(client):
    tid = published_tool(client)
    r = personalise(client, tid, {"client_name": "A", "topic": "B", "tax_year": "2026"})
    assert r.status_code == 400
    assert r.json() == {"detail": UNKNOWN_MESSAGE.format("tax_year"), "fields": ["tax_year"]}


def test_personalised_copies_are_never_stored(client):
    """Templates are stored clean (BRIEF.md): the values someone types in, which may be
    client details, are used for their copy and then forgotten."""
    tid = published_tool(client)
    conn = client.app.state.conn
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]

    def snapshot():
        return {t: conn.execute(f"SELECT * FROM {t}").fetchall() for t in tables}

    before = snapshot()
    assert personalise(client, tid, {"client_name": "Pat Example", "topic": "x"}).status_code == 200
    after = snapshot()
    assert [tuple(r) for t in tables for r in after[t]] == [tuple(r) for t in tables for r in before[t]]
    dump = "\n".join(conn.iterdump())
    assert "Pat Example" not in dump


def test_cannot_personalise_a_practice_only_tool_from_another_practice(client):
    tid = published_tool(client, visibility="practice-only", practice="Tax")
    r = personalise(client, tid, {"client_name": "A", "topic": "B"}, persona="u-tool-user")
    assert r.status_code == 403
    assert r.json() == {"detail": "Only published tools you can see can be personalized"}


def test_who_may_personalise_is_checked_before_the_values(client):
    """Someone who can't use the tool is told that, not which blanks are empty."""
    tid = published_tool(client, visibility="practice-only", practice="Tax")
    assert personalise(client, tid, {}, persona="u-tool-user").status_code == 403


def test_personalising_an_unknown_tool_is_404(client):
    assert personalise(client, 9999, {}).status_code == 404


# --- the screen only asks and displays ----------------------------------------------------

def page_script():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


def test_catalog_page_loads_the_list_from_the_back_end():
    page = page_script()
    assert 'loadOrExplain("/tools"' in page   # refusals show as the back end's words
    assert "coming next" not in page          # the placeholder is gone


def test_catalog_page_shows_what_the_back_end_supplies():
    page = page_script()
    for field in ("owner_name", "visibility_label", "rationale", "description",
                  "blanks", ".label", "filename"):
        assert field in page, f"the Catalog page doesn't show {field}"


def test_catalog_page_does_not_find_or_fill_blanks_itself():
    """The page never looks for {{...}} or fills the template: the back end's `blanks`
    say what to ask for, and its `text` is what gets downloaded."""
    page = page_script()
    assert "{{" not in page and "\\{\\{" not in page
    assert ".replace(" not in page and "replaceAll(" not in page
    assert "/personalize" in page and 'method: "POST"' in page


def test_catalog_page_leaves_checking_values_to_the_back_end():
    """No browser-side `required` boxes: the back end refuses empty values and its
    message is shown next to the boxes it names in `fields`."""
    page = page_script()
    assert not re.search(r"\brequired\b", page)
    assert "err.fields" in page


def test_download_helper_saves_the_back_ends_text_under_its_file_name():
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "export function saveTextFile" in js
    helper = js[js.index("export function saveTextFile"):]
    helper = helper[:helper.index("\n}\n")]
    assert "new Blob(" in helper and ".download = " in helper
    assert "revokeObjectURL" in helper   # tidy up after the download starts
    assert "saveTextFile(" in page_script()


def test_api_helper_passes_on_which_boxes_a_refusal_names():
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    api_helper = js[js.index("export async function api"):]
    api_helper = api_helper[:api_helper.index("\n}\n")]
    assert "error.fields" in api_helper


def test_page_scripts_contain_no_approval_rules():
    """The same guard as tests/test_web.py, for scripts written inside the pages."""
    persona_ids = {p["id"] for p in PERSONAS}
    for path in WEB_DIR.glob("*.html"):
        code = path.read_text(encoding="utf-8")
        for word in set(ROLES) | persona_ids:
            assert not re.search(rf"[\"'`]{re.escape(word)}[\"'`]", code), (
                f"{path.name} uses {word!r} as a value: keep that rule in the back end")
        assert "owner_id" not in code and ".role" not in code, path.name
