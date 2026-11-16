"""A simple HTTP API for the Tool Registry, built with FastAPI.

There is no real sign-in (DECISIONS.md #3). Each request says who is acting
with an `X-Persona` header holding a persona id, e.g. `X-Persona: u-builder`.
This stands in for the persona dropdown.

Run it locally:
    .venv/Scripts/python -m uvicorn registry.api:create_app --factory --reload
Then open http://127.0.0.1:8000/docs for a clickable page of every endpoint.
"""

import sqlite3

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from registry.approvals import (
    ApprovalInputError,
    ApprovalNotFound,
    current_step,
    decide,
    ensure_default_steps,
    get_history,
    get_progress,
    get_steps,
)
from registry.agent import get_ai_review
from registry.checks import get_check_results
from registry.db import connect
from registry.personas import ADMIN_ROLES, SPECIALIST_AREAS, get_user
from registry.seed import seed
from registry.tools import (
    NotAllowed,
    NotFound,
    ToolError,
    create_tool,
    get_tool,
    list_tools,
    render,
    submit_tool,
)

REVIEWER_ROLES = ("super_admin", "practice_admin", "specialist_reviewer")


# --- request bodies ---------------------------------------------------------------

class NewTool(BaseModel):
    name: str = Field(min_length=1)
    template: str = Field(min_length=1)
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


# --- helpers ------------------------------------------------------------------------

def can_see_published(user: sqlite3.Row, tool: dict) -> bool:
    """Firm-wide tools are visible to everyone; practice-only tools to that practice
    (and to Super admins)."""
    if tool["status"] != "published":
        return False
    if tool["visibility"] == "firm-wide" or user["role"] == "super_admin":
        return True
    return bool(user["practice"]) and user["practice"] == tool["practice"]


def tool_detail(conn: sqlite3.Connection, tool: dict) -> dict:
    checks = get_check_results(conn, tool["id"])
    return {
        **tool,
        "checks": checks,
        "flagged": any(not c["passed"] for c in checks),
        "ai_review": get_ai_review(conn, tool["id"]),  # advice only; never decides
        "current_step": current_step(conn, tool["id"]),
        "steps": get_progress(conn, tool["id"]),  # every step, for the progress line
        "history": get_history(conn, tool["id"]),
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
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(NotAllowed)
    async def _forbidden(request: Request, exc: NotAllowed):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ApprovalInputError)
    async def _bad_decision(request: Request, exc: ApprovalInputError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

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
        if user["role"] not in ADMIN_ROLES + ("specialist_reviewer",):
            raise HTTPException(
                403, "Admins and Specialist reviewers only (Practice admin, Super admin, "
                     "Specialist reviewer)")
        return user

    def load_tool(tool_id: int, conn: sqlite3.Connection) -> dict:
        tool = get_tool(conn, tool_id)
        if tool is None:
            raise NotFound(f"Tool {tool_id} not found")
        return tool

    # -- reference data (no persona needed: it feeds the persona dropdown) --

    @app.get("/personas")
    def personas(conn: sqlite3.Connection = Depends(db)):
        rows = conn.execute("SELECT id, name, role, practice, specialty FROM users ORDER BY id")
        return [dict(r) for r in rows]

    @app.get("/approval-steps")
    def approval_steps(conn: sqlite3.Connection = Depends(db)):
        return {"steps": get_steps(conn), "specialist_areas": SPECIALIST_AREAS}

    # -- catalogue and tools --

    @app.get("/tools")
    def catalogue(user=Depends(persona), conn=Depends(db)):
        """Published tools this persona can see."""
        return [t for t in list_tools(conn, status="published") if can_see_published(user, t)]

    @app.get("/my-tools")
    def my_tools(user=Depends(persona), conn=Depends(db)):
        rows = conn.execute("SELECT id FROM tools WHERE owner_id = ? ORDER BY id", (user["id"],))
        return [tool_detail(conn, get_tool(conn, r["id"])) for r in rows]

    @app.post("/tools", status_code=201)
    def new_tool(body: NewTool, user=Depends(persona), conn=Depends(db)):
        tool_id = create_tool(conn, owner_id=user["id"], **body.model_dump())
        return get_tool(conn, tool_id)

    @app.get("/tools/{tool_id}")
    def one_tool(tool_id: int, user=Depends(persona), conn=Depends(db)):
        tool = load_tool(tool_id, conn)
        allowed = (tool["owner_id"] == user["id"] or user["role"] in REVIEWER_ROLES
                   or can_see_published(user, tool))
        if not allowed:
            raise NotAllowed("You can't view this tool")
        return tool_detail(conn, tool)

    @app.post("/tools/{tool_id}/submit")
    def submit(tool_id: int, user=Depends(persona), conn=Depends(db)):
        return submit_tool(conn, tool_id, user["id"])

    @app.post("/tools/{tool_id}/decisions")
    def make_decision(tool_id: int, body: Decision, user=Depends(persona), conn=Depends(db)):
        load_tool(tool_id, conn)
        decide(conn, tool_id, user["id"], body.decision, body.comment,
               route_to=body.route_to, visibility=body.visibility, practice=body.practice)
        return tool_detail(conn, get_tool(conn, tool_id))

    @app.get("/tools/{tool_id}/history")
    def history(tool_id: int, user=Depends(persona), conn=Depends(db)):
        return one_tool(tool_id, user, conn)["history"]

    @app.post("/tools/{tool_id}/personalise")
    def personalise(tool_id: int, body: Personalise, user=Depends(persona), conn=Depends(db)):
        """Fill in a published tool's blanks to make this persona's own copy."""
        tool = load_tool(tool_id, conn)
        if not can_see_published(user, tool):
            raise NotAllowed("Only published tools you can see can be personalised")
        return {"tool_id": tool_id, "text": render(tool["template"], body.values)}

    # -- admin --

    @app.get("/admin/review-queue")
    def review_queue(user=Depends(queue_viewer), conn=Depends(db)):
        """Read-only: tools in review, with rule-based flags, the AI's advice, every
        approval step and the history. Admins see every tool in review; a Specialist
        reviewer sees only tools whose current step is a review for their area."""
        tools = list_tools(conn, status="in_review")
        if user["role"] == "specialist_reviewer":
            def waiting_for_me(tool):
                step = current_step(conn, tool["id"])
                return (step is not None and step["action"] == "review"
                        and step["area"] == user["specialty"])
            tools = [t for t in tools if waiting_for_me(t)]
        return [tool_detail(conn, t) for t in tools]

    return app
