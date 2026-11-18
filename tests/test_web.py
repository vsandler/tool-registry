"""The pages are served, every page has the shared layout, and the front end holds no
approval rules: it only asks the back end and displays the answer (DECISIONS.md #12)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from registry.api import create_app
from registry.personas import PERSONAS, ROLES

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
PAGES = {"/app/": "Catalog", "/app/submit.html": "Submit a tool",
         "/app/queue.html": "Review queue"}


@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


# --- the pages are served -------------------------------------------------------------

def test_home_address_opens_the_app(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/app/"


@pytest.mark.parametrize("path, title", PAGES.items())
def test_every_page_loads_with_the_shared_layout(client, path, title):
    r = client.get(path)  # no X-Persona header: pages load before a persona is picked
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert f"<title>{title}" in html
    assert 'id="layout"' in html            # banner, persona dropdown and navigation go here
    assert 'src="app.js"' in html or "from \"./app.js\"" in html or "from './app.js'" in html
    assert 'href="style.css"' in html


def test_shared_script_and_styles_are_served(client):
    js = client.get("/app/app.js")
    css = client.get("/app/style.css")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")


def test_layout_has_the_banner_dropdown_and_navigation():
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "Demo: pick a persona, no real sign-in" in js
    # A dropdown with id "persona", and a label pointing at it (for screen readers).
    assert 'h(\n    "select",\n    { id: "persona"' in js
    assert 'h("label", { for: "persona" }' in js
    for page, name in (("./", "Catalog"), ("submit.html", "Submit a tool"),
                       ("queue.html", "Review queue")):
        assert page in js and name in js


def test_unknown_page_is_404(client):
    assert client.get("/app/nope.html").status_code == 404


def test_api_addresses_still_work_alongside_the_pages(client):
    assert client.get("/personas").status_code == 200
    assert client.get("/tools", headers={"X-Persona": "u-tool-user"}).status_code == 200


# --- the back end supplies labels and permissions; the screens just show them -------------------

def test_personas_come_with_a_ready_made_label(client):
    people = {p["id"]: p for p in client.get("/personas").json()}
    assert people["u-specialist"]["label"] == "Sam Thistle: Specialist reviewer, Compliance"
    assert people["u-specialist-tech"]["label"] == (
        "Devon Marsh: Specialist reviewer, AI enablement (technology)")
    assert people["u-builder"]["label"] == "Avery Quill: Builder, Tax"
    assert people["u-super-admin"]["label"] == "Riley Ashgrove: Super admin"


def test_can_open_queue_matches_what_the_queue_actually_allows(client):
    """The navigation shows the Review queue link only if the back end says so, and
    that flag must agree with the queue itself for every persona."""
    for person in client.get("/personas").json():
        r = client.get("/admin/review-queue", headers={"X-Persona": person["id"]})
        assert person["can_open_queue"] == (r.status_code == 200), person["id"]
    assert {p["id"] for p in client.get("/personas").json() if not p["can_open_queue"]} == {
        "u-builder", "u-tool-user"}


QUEUE_REFUSED = ("The Review queue is only for Practice admins, Super admins and "
                 "Specialist reviewers. Pick one of those personas to see it.")


@pytest.mark.parametrize("persona", ["u-builder", "u-tool-user"])
def test_queue_refusal_is_a_plain_sentence(client, persona):
    r = client.get("/admin/review-queue", headers={"X-Persona": persona})
    assert r.status_code == 403
    assert r.json() == {"detail": QUEUE_REFUSED}


def test_queue_page_shows_the_back_ends_message_on_screen():
    """Typing the Review queue address as a persona who can't open it must show the
    back end's message on screen, not a blank page or an error code. Without browser
    tests (DECISIONS.md #12) this checks the wiring:
    - api() turns a refusal into an error carrying the back end's `detail` text;
    - loadOrExplain() writes that text into the page, in an alert the screen reader reads;
    - the queue page loads the queue through loadOrExplain()."""
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    page = (WEB_DIR / "queue.html").read_text(encoding="utf-8")
    assert "data.detail" in js                                  # uses the back end's words
    assert "export async function loadOrExplain" in js
    load_or_explain = js[js.index("export async function loadOrExplain"):]
    load_or_explain = load_or_explain[:load_or_explain.index("\n}\n")]
    assert "showMessage(" in load_or_explain and "err.message" in load_or_explain
    show_message = js[js.index("export function showMessage"):]
    show_message = show_message[:show_message.index("\n}\n")]
    assert '"alert"' in show_message                            # announced, not just drawn
    assert 'loadOrExplain("/admin/review-queue"' in page


def test_every_decision_refusal_from_the_api_is_a_plain_sentence(client):
    """Each kind of refusal an approve or reject can get comes back with a readable
    `detail` sentence the screen can show next to the buttons."""
    headers = {"X-Persona": "u-builder"}
    tid = client.post("/tools", headers=headers, json=dict(
        name="Refusal tool", template="Hi {{name}}", visibility="firm-wide",
        rationale="A clear, reusable greeting.")).json()["id"]
    client.post(f"/tools/{tid}/submit", headers=headers)

    def attempt(persona, **body):
        return client.post(f"/tools/{tid}/decisions", headers={"X-Persona": persona}, json=body)

    refusals = [
        attempt("u-builder", decision="approved", route_to="compliance"),      # own tool
        attempt("u-specialist", decision="approved"),                          # not their turn
        attempt("u-super-admin", decision="approved"),                         # no area chosen
        attempt("u-super-admin", decision="rejected", comment="no"),           # comment too short
        attempt("u-super-admin", decision="maybe"),                            # not a decision
    ]
    for r in refusals:
        assert r.status_code in (400, 403), r.text
        detail = r.json()["detail"]
        assert isinstance(detail, str) and len(detail) > 15, r.text   # a sentence, not a code
    assert refusals[3].json()["field"] == "comment"   # so it goes next to the comment box


def test_decision_refusals_are_shown_next_to_the_buttons():
    """decideOrExplain() posts the decision and, if it's refused, shows the back end's
    message on screen next to the buttons, or next to the comment box when the problem
    is the comment, the same way the Review queue refusal is shown."""
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "export async function decideOrExplain" in js
    helper = js[js.index("export async function decideOrExplain"):]
    helper = helper[:helper.index("\n}\n")]
    assert "/decisions" in helper and 'method: "POST"' in helper
    assert "showMessage(target, err.message)" in helper            # the back end's words
    assert 'err.field === "comment"' in helper and "commentArea" in helper
    assert "buttonsArea" in helper


def test_no_page_posts_a_decision_without_the_helper():
    """Guard: approve and reject buttons must go through decideOrExplain(), so no
    refusal can end up silent. A page calling the decisions address itself fails this."""
    for path in list(WEB_DIR.glob("*.html")) + list(WEB_DIR.glob("*.js")):
        code = path.read_text(encoding="utf-8")
        if path.name == "app.js":
            code = code.replace(code[code.index("export async function decideOrExplain"):]
                                .split("\n}\n")[0], "")
        assert "/decisions" not in code, (
            f"{path.name} posts a decision directly: use decideOrExplain() from app.js")


def test_front_end_contains_no_approval_rules():
    """Guard: the browser code never checks roles, owners or areas itself. If a role
    name or an owner check appears in the JavaScript, a rule has leaked out of the
    back end (DECISIONS.md #12). Ask the API (my_action, can_open_queue) instead."""
    persona_ids = {p["id"] for p in PERSONAS}
    scripts = list(WEB_DIR.glob("*.js"))
    assert scripts, "no JavaScript found in web/"
    for path in scripts:
        code = path.read_text(encoding="utf-8")
        for word in set(ROLES) | persona_ids:
            # A role or persona id written as a value, e.g. role === "super_admin".
            assert not re.search(rf"[\"'`]{re.escape(word)}[\"'`]", code), (
                f"{path.name} uses {word!r} as a value: keep that rule in the back end")
        assert "owner_id" not in code, f"{path.name} compares owners: keep that in the back end"
        assert ".role" not in code, f"{path.name} reads a role: ask the API instead"


# --- no screen ever shows "null" ------------------------------------------------------------------

def _web_code():
    return {path.name: path.read_text(encoding="utf-8")
            for path in sorted(WEB_DIR.iterdir()) if path.suffix in (".html", ".js")}


def _function_body(js, name):
    start = js.index(f"export function {name}(")
    return js[start:js.index("\n}\n", start)]


def test_no_screen_ever_shows_null():
    """The browser's replaceChildren() and append() turn an empty value into the text
    "null" (a tool with no description showed "nullnull"). Pages put content on screen
    only through h() and fill(), which skip empty values."""
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    fill = _function_body(js, "fill")
    assert "null" in fill and "undefined" in fill and "false" in fill
    builder = _function_body(js, "h")
    assert "child === null" in builder and "child === undefined" in builder

    for name, code in _web_code().items():
        if name == "app.js":  # the two helpers that do it safely, and the download link
            code = code.replace(fill, "").replace(builder, "")
            code = code.replace("document.body.append(link)", "")
        for match in re.finditer(r"\.(replaceChildren|append|prepend|before|after)\(\s*(\S)",
                                 code):
            if match.group(1) == "replaceChildren" and match.group(2) == ")":
                continue  # clearing a box, with nothing to show
            line = code[:match.start()].count("\n") + 1
            raise AssertionError(f"{name} (about line {line}) puts content on screen "
                                 "without fill() or h()")


def test_dates_that_are_missing_show_nothing():
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    when = _function_body(js, "when")
    assert 'if (!iso) return "";' in when  # not "1 Jan 1970" or "null"
