"""The AI pre-review runs on every submit, and its verdict is advice only.

The real AI is replaced by the `fake_ai` stand-in from conftest.py.
"""

import pytest
from fastapi.testclient import TestClient

from registry import agent
from registry.api import create_app
from registry.approvals import current_step, decide, ensure_default_steps, get_history
from registry.tools import create_tool, get_tool, submit_tool

RATIONALE = "Kept short so it's easy to reuse across the practice."


def new_submitted_tool(conn, name="AI test tool"):
    ensure_default_steps(conn)
    tid = create_tool(conn, name=name, template="Hello {{name}}", owner_id="u-builder",
                      visibility="firm-wide", rationale=RATIONALE)
    return tid, submit_tool(conn, tid, "u-builder")


# --- it runs, and it's saved ---------------------------------------------------------

def test_submit_runs_the_ai_once_on_the_submitted_tool(conn, fake_ai):
    tid, _ = new_submitted_tool(conn)
    assert len(fake_ai.calls) == 1
    assert fake_ai.calls[0]["id"] == tid


def test_submit_saves_and_returns_the_ai_advice(conn, fake_ai):
    fake_ai.verdict = "risky"
    tid, result = new_submitted_tool(conn)
    advice = result["ai_review"]
    assert advice["advice_only"] is True
    assert advice["verdict"] == "risky"
    assert advice["flagged"] is True
    assert advice["issues"] == ["Fake issue for testing."]
    assert agent.get_ai_review(conn, tid) == advice


def test_tool_never_submitted_has_no_ai_advice(conn):
    tid = create_tool(conn, name="Draft", template="x", owner_id="u-builder",
                      visibility="firm-wide")
    assert agent.get_ai_review(conn, tid) is None


def test_ai_does_not_run_when_submit_is_refused(conn, fake_ai):
    tid = create_tool(conn, name="T", template="x", owner_id="u-builder", visibility="firm-wide")
    with pytest.raises(Exception):
        submit_tool(conn, tid, "u-practice-admin")  # not the owner
    assert fake_ai.calls == []


# --- advice only: it never approves or rejects --------------------------------------

def test_ai_safe_does_not_approve_anything(conn, fake_ai):
    fake_ai.verdict = "safe"
    tid, _ = new_submitted_tool(conn)
    assert get_tool(conn, tid)["status"] == "in_review"
    assert current_step(conn, tid)["action"] == "route"  # still waiting at step 1
    assert get_history(conn, tid) == []                    # no decision recorded


def test_ai_risky_does_not_reject_and_humans_can_still_publish(conn, fake_ai):
    fake_ai.verdict = "risky"
    tid, _ = new_submitted_tool(conn)
    assert get_tool(conn, tid)["status"] == "in_review"
    decide(conn, tid, "u-super-admin", "approved", route_to="compliance")
    decide(conn, tid, "u-specialist", "approved")
    decide(conn, tid, "u-super-admin", "approved", visibility="firm-wide")
    assert get_tool(conn, tid)["status"] == "published"


def test_ai_verdict_does_not_change_rule_based_flag(conn, fake_ai):
    fake_ai.verdict = "risky"
    _, result = new_submitted_tool(conn)
    assert result["flagged"] is False  # every rule-based check passed
    assert result["ai_review"]["flagged"] is True


# --- a broken AI never blocks a submission -------------------------------------------

def test_unexpected_ai_crash_still_submits_and_flags_for_a_human(conn, fake_ai):
    fake_ai.error = RuntimeError("something broke")
    tid, result = new_submitted_tool(conn)
    assert get_tool(conn, tid)["status"] == "in_review"
    assert result["ai_review"]["verdict"] == "needs_human"
    assert result["ai_review"]["flagged"] is True


def test_needs_human_verdict_is_stored(conn, fake_ai):
    fake_ai.verdict = "needs_human"
    tid, _ = new_submitted_tool(conn)
    assert agent.get_ai_review(conn, tid)["verdict"] == "needs_human"


# --- shown to reviewers in the admin queue -------------------------------------------

@pytest.fixture
def client():
    with TestClient(create_app(":memory:")) as c:
        yield c


def test_review_queue_shows_ai_advice_for_every_tool(client):
    queue = client.get("/admin/review-queue", headers={"X-Persona": "u-super-admin"}).json()
    assert queue
    for tool in queue:
        assert tool["ai_review"]["advice_only"] is True
        assert tool["ai_review"]["verdict"] in ("risky", "safe", "needs_human")


def test_submit_endpoint_returns_ai_advice(client, fake_ai):
    fake_ai.verdict = "risky"
    headers = {"X-Persona": "u-builder"}
    tid = client.post("/tools", headers=headers, json=dict(
        name="Endpoint tool", template="Hi {{name}}", visibility="firm-wide",
        rationale=RATIONALE)).json()["id"]
    body = client.post(f"/tools/{tid}/submit", headers=headers).json()
    assert body["ai_review"]["verdict"] == "risky"
    assert body["tool"]["status"] == "in_review"
