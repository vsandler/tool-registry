"""A simple HTTP API for the Tool Registry, built with FastAPI.

There is no real sign-in (DECISIONS.md #3). Each request says who is acting
with an `X-Persona` header holding a persona id, e.g. `X-Persona: u-builder`.
This stands in for the persona dropdown.

Run it locally:
    .venv/Scripts/python -m uvicorn registry.api:create_app --factory --reload
Then open http://127.0.0.1:8000/ for the app (the screens, served from web/), or
http://127.0.0.1:8000/docs for a clickable page of every endpoint.
"""

import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from registry.approvals import (
    ApprovalInputError,
    ApprovalNotFound,
    current_step,
    decide,
    ensure_default_steps,
    get_history,
    get_progress,
    get_rejection,
    get_steps,
    my_action,
)
from registry.agent import get_ai_review
from registry.checks import MIN_RATIONALE_LENGTH, get_check_results
from registry.db import connect
from registry.personas import (
    QUEUE_ROLES,
    SPECIALIST_AREAS,
    get_user,
    SUBMIT_ROLES,
    persona_label,
    practice_names,
)
from registry.seed import seed
from registry.tools import (
    check_can_submit,
    NotAllowed,
    NotFound,
    ToolError,
    FORM_FIELDS,
    VISIBILITY_OPTIONS,
    blanks_for,
    create_and_submit,
    create_tool,
    download_filename,
    get_tool,
    list_tools,
    personalise as fill_in_blanks,
    submit_tool,
)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"  # the screens (DECISIONS.md #12)

# Shown on screen if someone who can't open the Review queue reaches it anyway.
QUEUE_REFUSED_MESSAGE = ("The Review queue is only for Practice admins, Super admins and "
                         "Specialist reviewers. Pick one of those personas to see it.")


# --- request bodies ---------------------------------------------------------------

class NewTool(BaseModel):
    # Empty names and templates are refused by create_tool with a plain sentence
    # naming the boxes, rather than by a length rule here (which gives a bare 422).
    name: str
    template: str
    visibility: str
    description: str = ""
    practice: str | None = None
    rationale: str = ""
    variables: list[str] | None = None


class Decision(BaseModel):
    decision: str  # "approved" or "rejected"
    comment: str = ""
    # Step 1: one area, or a list of areas in review order
    # (technology, compliance, marketing).
    route_to: str | list[str] | None = None
    visibility: str | None = None  # step 3: practice-only or firm-wide
    practice: str | None = None    # step 3, practice-only


class Personalise(BaseModel):
    values: dict[str, str]


class TemplateText(BaseModel):
    template: str = ""


# --- helpers ------------------------------------------------------------------------

def can_see_published(user: sqlite3.Row, tool: dict) -> bool:
    """Firm-wide tools are visible to everyone; practice-only tools to that practice
    (and to Super admins)."""
    if tool["status"] != "published":
        return False
    if tool["visibility"] == "firm-wide" or user["role"] == "super_admin":
        return True
    return bool(user["practice"]) and user["practice"] == tool["practice"]


SPECIALIST_NOT_YOUR_AREA = "This tool isn't waiting for your area's review."
OTHER_PRACTICE = "This tool belongs to another practice."


def tool_practice(conn: sqlite3.Connection, tool: dict) -> str | None:
    """A tool belongs to its owner's practice (DECISIONS.md #13). Every builder has
    one; owners without a practice (for example Specialists) give None."""
    owner = get_user(conn, tool["owner_id"])
    return owner["practice"] if owner else None


def practice_admin_may_see(conn: sqlite3.Connection, user: sqlite3.Row, tool: dict) -> bool:
    return bool(user["practice"]) and tool_practice(conn, tool) == user["practice"]


def check_can_view(conn: sqlite3.Connection, user: sqlite3.Row, tool: dict) -> None:
    """Who may see a tool's details (DECISIONS.md #13). Raises NotAllowed if not.

    - The owner, always. The Super admin, always.
    - Anyone, once it's published and visible to them in the catalogue.
    - A Practice admin only for tools from their own practice (the owner's practice).
    - A Specialist reviewer only while its current step is a review for their area,
      or if they already decided a step of it (least privilege).
    """
    if tool["owner_id"] == user["id"] or user["role"] == "super_admin":
        return
    if can_see_published(user, tool):
        return
    if user["role"] == "practice_admin":
        if practice_admin_may_see(conn, user, tool):
            return
        raise NotAllowed(OTHER_PRACTICE)
    if user["role"] == "specialist_reviewer":
        step = current_step(conn, tool["id"])
        if step and step["action"] == "review" and step["area"] == user["specialty"]:
            return
        if any(h["approver_id"] == user["id"] for h in get_history(conn, tool["id"])):
            return
        raise NotAllowed(SPECIALIST_NOT_YOUR_AREA)
    raise NotAllowed("You can't view this tool")


# What the Catalog shows about each tool. Review internals (rule flags, AI advice,
# steps, history and reviewers' comments) are left out: they belong to reviewing.
CATALOGUE_FIELDS = ("id", "name", "description", "template", "rationale",
                    "visibility", "practice")


def visibility_label(tool: dict) -> str:
    if tool["visibility"] == "practice-only":
        return f"Practice-only: {tool['practice']}" if tool["practice"] else "Practice-only"
    return "Firm-wide"


def catalogue_entry(conn: sqlite3.Connection, tool: dict) -> dict:
    """One published tool, ready for the Catalog screen to display as-is."""
    owner = get_user(conn, tool["owner_id"])
    return {
        **{k: tool[k] for k in CATALOGUE_FIELDS},
        "visibility_label": visibility_label(tool),
        "owner_name": owner["name"] if owner else "Unknown",
        "blanks": blanks_for(tool["template"]),  # what to ask for, from the template itself
    }


# A tool's status as the screens show it.
STATUS_LABELS = {"draft": "Draft", "in_review": "In review", "rejected": "Rejected",
                 "published": "Published"}


def published_label(tool: dict) -> str | None:
    """Where a published tool went, in words, e.g. "Published firm-wide" or
    "Published to the Tax practice only". None until it's published."""
    if tool["status"] != "published":
        return None
    if tool["visibility"] == "practice-only":
        if tool["practice"]:
            return f"Published to the {tool['practice']} practice only"
        return "Published to one practice only"
    return "Published firm-wide"


def published_badge(tool: dict) -> str | None:
    """The same, short enough for a badge next to the tool's name, e.g.
    "Published · Firm-wide" or "Published · Tax practice only". None until published."""
    if tool["status"] != "published":
        return None
    if tool["visibility"] == "practice-only":
        if tool["practice"]:
            return f"Published · {tool['practice']} practice only"
        return "Published · One practice only"
    return "Published · Firm-wide"


def tool_detail(conn: sqlite3.Connection, tool: dict, viewer: sqlite3.Row | None = None) -> dict:
    """Everything the screens show about one tool. `my_action` is for the persona
    viewing it: can they decide the current step, and if not, why (plain words)."""
    checks = get_check_results(conn, tool["id"])
    owner = get_user(conn, tool["owner_id"])
    return {
        **tool,
        "owner_name": owner["name"] if owner else "Unknown",
        "status_label": STATUS_LABELS.get(tool["status"], tool["status"]),
        "published_label": published_label(tool),
        "published_badge": published_badge(tool),
        "checks": checks,
        "flagged": any(not c["passed"] for c in checks),
        "ai_review": get_ai_review(conn, tool["id"]),  # advice only; never decides
        "current_step": current_step(conn, tool["id"]),
        "steps": get_progress(conn, tool["id"]),  # every step, for the progress line
        "rejection": get_rejection(conn, tool["id"]),  # who, when, which step, why
        "history": get_history(conn, tool["id"]),
        "my_action": my_action(conn, tool["id"], viewer["id"]) if viewer else None,
    }


# --- the app -----------------------------------------------------------------------

def create_app(db_path: str = "registry.db") -> FastAPI:
    conn = connect(db_path)
    if conn.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
        seed(conn)  # first run: load the made-up sample data
    ensure_default_steps(conn)

    app = FastAPI(title="Tool Registry", description="Made-up demo data only.")
    app.state.conn = conn

    @app.exception_handler(ToolError)
    async def _bad_request(request: Request, exc: ToolError):
        content = {"detail": str(exc)}
        if getattr(exc, "fields", None):  # tells a form which boxes the message is about
            content["fields"] = exc.fields
        if getattr(exc, "messages", None):  # one message per box, to show next to each
            content["messages"] = exc.messages
        return JSONResponse(status_code=400, content=content)

    @app.exception_handler(NotAllowed)
    async def _forbidden(request: Request, exc: NotAllowed):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ApprovalInputError)
    async def _bad_decision(request: Request, exc: ApprovalInputError):
        content = {"detail": str(exc)}
        if getattr(exc, "field", None):  # tells a form which box the message belongs to
            content["field"] = exc.field
        return JSONResponse(status_code=400, content=content)

    @app.exception_handler(NotFound)
    @app.exception_handler(ApprovalNotFound)  # listed explicitly: it is also a NotAllowed
    async def _not_found(request: Request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    def db() -> sqlite3.Connection:
        return app.state.conn

    def persona(x_persona: str = Header(..., description="Persona id, e.g. u-builder"),
                conn: sqlite3.Connection = Depends(db)) -> sqlite3.Row:
        user = get_user(conn, x_persona)
        if user is None:
            raise HTTPException(401, f"Unknown persona {x_persona!r}")
        return user

    def queue_viewer(user: sqlite3.Row = Depends(persona)) -> sqlite3.Row:
        """Admins see the whole Review queue; Specialist reviewers see only their
        area's work (DECISIONS.md #10, option A). Everyone else is refused."""
        if user["role"] not in QUEUE_ROLES:
            raise HTTPException(403, QUEUE_REFUSED_MESSAGE)
        return user

    def load_tool(tool_id: int, conn: sqlite3.Connection) -> dict:
        tool = get_tool(conn, tool_id)
        if tool is None:
            raise NotFound(f"Tool {tool_id} not found")
        return tool

    # -- reference data (no persona needed: it feeds the persona dropdown) --

    @app.get("/personas")
    def personas(conn: sqlite3.Connection = Depends(db)):
        """For the persona dropdown: each person with a ready-made `label`, and
        `can_open_queue` so the navigation shows the Review queue link only to those
        the queue lets in (the same QUEUE_ROLES the queue itself checks)."""
        rows = conn.execute("SELECT id, name, role, practice, specialty FROM users ORDER BY id")
        return [{**dict(r), "label": persona_label(r), "can_open_queue": r["role"] in QUEUE_ROLES,
                 "can_submit": r["role"] in SUBMIT_ROLES}
                for r in rows]

    # -- the screens --

    @app.get("/", include_in_schema=False)
    def home():
        return RedirectResponse("/app/")

    app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="app")

    # -- the Submit form --

    @app.get("/submit-form")
    def submit_form(user=Depends(persona), conn=Depends(db)):
        check_can_submit(conn, user["id"])
        """The Submit form's boxes (label, hint, and whether it's required) and its
        choices: visibility options (each saying whether it needs a practice), the
        practices people belong to, this persona's own practice to start with, and the
        shortest rationale the checks accept without a flag."""
        return {"fields": FORM_FIELDS, "visibilities": VISIBILITY_OPTIONS,
                "practices": practice_names(conn),
                "default_practice": user["practice"], "rationale_min": MIN_RATIONALE_LENGTH}

    @app.post("/templates/blanks")
    def template_blanks(body: TemplateText):
        """The {{blanks}} in a template, for the Submit form's live list. Saves
        nothing, so it needs no persona."""
        return {"blanks": blanks_for(body.template)}

    @app.get("/approval-steps")
    def approval_steps(conn: sqlite3.Connection = Depends(db)):
        return {"steps": get_steps(conn), "specialist_areas": SPECIALIST_AREAS}

    # -- catalogue and tools --

    @app.get("/tools")
    def catalogue(user=Depends(persona), conn=Depends(db)):
        """Published tools this persona can see, each with its owner's name, a
        visibility label and the blanks to fill in when personalising."""
        return [catalogue_entry(conn, t) for t in list_tools(conn, status="published")
                if can_see_published(user, t)]

    @app.get("/my-tools")
    def my_tools(user=Depends(persona), conn=Depends(db)):
        rows = conn.execute("SELECT id FROM tools WHERE owner_id = ? ORDER BY id", (user["id"],))
        return [tool_detail(conn, get_tool(conn, r["id"]), user) for r in rows]

    @app.post("/tools", status_code=201)
    def new_tool(body: NewTool, user=Depends(persona), conn=Depends(db)):
        tool_id = create_tool(conn, owner_id=user["id"], **body.model_dump())
        return get_tool(conn, tool_id)

    @app.post("/submissions", status_code=201)
    def submit_new(body: NewTool, user=Depends(persona), conn=Depends(db)):
        """The Submit form: check everything, then save the tool and send it for review
        in one go. A refusal names every box with a problem and saves nothing. Flags
        never block: a flagged tool goes into review with its flags."""
        return create_and_submit(conn, user["id"], **body.model_dump())

    @app.get("/tools/{tool_id}")
    def one_tool(tool_id: int, user=Depends(persona), conn=Depends(db)):
        tool = load_tool(tool_id, conn)
        check_can_view(conn, user, tool)
        return tool_detail(conn, tool, user)

    @app.post("/tools/{tool_id}/submit")
    def submit(tool_id: int, user=Depends(persona), conn=Depends(db)):
        return submit_tool(conn, tool_id, user["id"])

    @app.post("/tools/{tool_id}/decisions")
    def make_decision(tool_id: int, body: Decision, user=Depends(persona), conn=Depends(db)):
        load_tool(tool_id, conn)
        decide(conn, tool_id, user["id"], body.decision, body.comment,
               route_to=body.route_to, visibility=body.visibility, practice=body.practice)
        return tool_detail(conn, get_tool(conn, tool_id), user)

    @app.get("/tools/{tool_id}/history")
    def history(tool_id: int, user=Depends(persona), conn=Depends(db)):
        return one_tool(tool_id, user, conn)["history"]

    @app.post("/tools/{tool_id}/personalise")
    def personalise(tool_id: int, body: Personalise, user=Depends(persona), conn=Depends(db)):
        """Fill in a published tool's blanks to make this persona's own copy, to
        download. Every blank needs a value; a refusal names the boxes in `fields`.
        Nothing is saved: the values may be client details."""
        tool = load_tool(tool_id, conn)
        if not can_see_published(user, tool):
            raise NotAllowed("Only published tools you can see can be personalised")
        return {"tool_id": tool_id, "text": fill_in_blanks(tool["template"], body.values),
                "filename": download_filename(tool["name"])}

    # -- admin --

    @app.get("/admin/review-queue")
    def review_queue(user=Depends(queue_viewer), conn=Depends(db)):
        """Read-only: tools in review, with rule-based flags, the AI's advice, every
        approval step and the history. The Super admin sees every tool in review; a
        Practice admin sees only their own practice's tools (the owner's practice); a
        Specialist reviewer sees only tools whose current step is a review for their area.
        Oldest submitted first, so tools that have waited longest come first."""
        tools = sorted(list_tools(conn, status="in_review"),
                       key=lambda t: (t["submitted_at"] or t["created_at"], t["id"]))
        if user["role"] == "practice_admin":
            tools = [t for t in tools if practice_admin_may_see(conn, user, t)]
        if user["role"] == "specialist_reviewer":
            def waiting_for_me(tool):
                step = current_step(conn, tool["id"])
                return (step is not None and step["action"] == "review"
                        and step["area"] == user["specialty"])
            tools = [t for t in tools if waiting_for_me(t)]
        return [tool_detail(conn, t, user) for t in tools]

    return app
