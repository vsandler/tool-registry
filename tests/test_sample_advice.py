"""Fixed sample advice for the seeded demo tools, the demo drafts, and the refresh script.

The real AI is replaced by the `fake_ai` stand-in from conftest.py.
"""

import ast
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from registry import agent, sample_advice
from registry.api import create_app
from registry.checks import run_checks
from registry.db import connect
from registry.refresh_sample_advice import refresh
from registry.seed import DEMO_DRAFTS, FAILING_TOOL, SAFE_TOOLS, seed
from registry.tools import get_tool, submit_tool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEEDED_NAMES = {t["name"] for t in SAFE_TOOLS + [FAILING_TOOL]}


# --- the warning test: fails when the sample advice goes stale -----------------------

def test_sample_advice_matches_current_model_and_instructions():
    problems = sample_advice.staleness_problems()
    assert not problems, sample_advice.explain(problems)


def test_staleness_check_spots_a_model_change():
    data = {**sample_advice.load(), "model": "some-older-model",
            "instructions_fingerprint": agent.instructions_fingerprint()}
    problems = sample_advice.staleness_problems(data, config={"model": "claude-haiku-5-5"})
    assert len(problems) == 1 and "model changed" in problems[0]


def test_staleness_check_spots_an_instructions_change():
    data = {**sample_advice.load(), "model": "claude-haiku-5-5",
            "instructions_fingerprint": "0" * 64}
    problems = sample_advice.staleness_problems(data, config={"model": "claude-haiku-5-5"})
    assert len(problems) == 1 and "instructions changed" in problems[0]


def current_data():
    """The stored sample advice, but stamped as up to date for the current model and
    instructions, so a test only sees the one problem it sets up itself."""
    return {**sample_advice.load(), "model": "claude-haiku-5-5",
            "instructions_fingerprint": agent.instructions_fingerprint()}


HAIKU = {"model": "claude-haiku-5-5"}


def test_staleness_check_spots_a_changed_seeded_tool():
    tools = sample_advice.seeded_tools()
    tools[2] = {**tools[2], "template": tools[2]["template"] + " Extra sentence."}
    problems = sample_advice.staleness_problems(current_data(), HAIKU, tools)
    assert problems == [
        "A seeded tool changed: 'Client welcome letter' in registry/seed.py is different "
        "from the version the sample advice was written for."
    ]
    assert "registry/seed.py" in sample_advice.explain(problems)


def test_staleness_check_spots_a_new_seeded_tool_without_advice():
    tools = sample_advice.seeded_tools() + [{"name": "Brand new tool", "template": "x"}]
    problems = sample_advice.staleness_problems(current_data(), HAIKU, tools)
    assert len(problems) == 1 and "'Brand new tool'" in problems[0]


def test_staleness_check_spots_advice_for_a_removed_seeded_tool():
    problems = sample_advice.staleness_problems(current_data(), HAIKU,
                                                sample_advice.seeded_tools()[:2])
    assert len(problems) == 1 and "no longer a seeded tool" in problems[0]


def test_tool_fingerprint_covers_what_the_ai_reads_and_nothing_else():
    tool = sample_advice.seeded_tools()[0]
    base = sample_advice.tool_fingerprint(tool)
    for field in agent.SUBMISSION_FIELDS:
        assert sample_advice.tool_fingerprint({**tool, field: "changed"}) != base, field
    # The database id, owner and timestamps aren't sent to the AI, so they don't count.
    assert sample_advice.tool_fingerprint({**tool, "id": 999, "owner_id": "u-other",
                                           "created_at": "2030-01-01"}) == base


def test_fingerprint_changes_when_instructions_change():
    base = agent.instructions_fingerprint()
    assert agent.instructions_fingerprint(agent.SYSTEM_PROMPT + " ") != base
    assert agent.instructions_fingerprint(schema={**agent.RESPONSE_SCHEMA, "x": 1}) != base
    assert agent.instructions_fingerprint() == base  # same input, same fingerprint


def test_failure_message_explains_steps_and_command():
    message = sample_advice.explain(["The model changed."])
    assert "The model changed." in message
    assert sample_advice.REFRESH_COMMAND in message
    for step in ("1.", "2.", "3.", "4."):
        assert step in message


# --- seeding uses the sample advice, with no AI calls --------------------------------

def test_sample_advice_covers_exactly_the_seeded_submissions():
    assert set(sample_advice.load()["advice"]) == SEEDED_NAMES


def test_seeding_makes_no_ai_calls(conn, fake_ai):
    seed(conn)
    assert fake_ai.calls == []


def test_seeded_tools_show_labelled_sample_advice(conn):
    ids = seed(conn)
    stored = sample_advice.load()["advice"]
    for name in SEEDED_NAMES:
        advice = agent.get_ai_review(conn, ids[name])
        assert advice["sample"] is True
        assert advice["label"] == agent.SAMPLE_LABEL
        assert advice["advice_only"] is True
        assert advice["verdict"] == stored[name]["verdict"]
        assert advice["issues"] == stored[name]["issues"]


def test_starting_the_app_makes_no_ai_calls(fake_ai):
    with TestClient(create_app(":memory:")) as client:
        queue = client.get("/admin/review-queue", headers={"X-Persona": "u-super-admin"}).json()
    assert fake_ai.calls == []
    assert all(t["ai_review"]["sample"] for t in queue)


# --- demo drafts -----------------------------------------------------------------------

def test_demo_drafts_are_saved_but_not_submitted(conn):
    ids = seed(conn)
    for spec in DEMO_DRAFTS:
        assert get_tool(conn, ids[spec["name"]])["status"] == "draft"
        assert agent.get_ai_review(conn, ids[spec["name"]]) is None


def test_demo_drafts_pass_every_rule_based_check(conn):
    """So any flag on the subtly risky draft comes from the AI alone."""
    ids = seed(conn)
    for spec in DEMO_DRAFTS:
        failed = [r.name for r in run_checks(conn, get_tool(conn, ids[spec["name"]]))
                  if not r.passed]
        assert failed == [], spec["name"]


def test_submitting_a_demo_draft_calls_the_real_ai(conn, fake_ai):
    ids = seed(conn)
    result = submit_tool(conn, ids["Savings check-in note"], "u-builder")
    assert len(fake_ai.calls) == 1
    assert result["ai_review"]["sample"] is False
    assert "label" not in result["ai_review"]


# --- only the seed setup can pass sample_advice ----------------------------------------

def test_api_submit_route_cannot_pass_sample_advice(fake_ai):
    """Even if a caller sends sample advice in the request, the route ignores it and
    the real AI (here the fake) is called."""
    with TestClient(create_app(":memory:")) as client:
        headers = {"X-Persona": "u-builder"}
        tid = client.post("/tools", headers=headers, json=dict(
            name="Sneaky tool", template="Hi {{name}}", visibility="firm-wide",
            rationale="Kept short so it's easy to reuse across the practice.")).json()["id"]
        fake_ai.verdict = "risky"
        body = client.post(f"/tools/{tid}/submit", headers=headers, json={
            "sample_advice": {"verdict": "safe", "issues": [], "reason": "Trust me."},
        }).json()
    assert len(fake_ai.calls) == 1
    assert body["ai_review"]["sample"] is False
    assert body["ai_review"]["verdict"] == "risky"


def test_only_seed_py_passes_sample_advice_in_the_code():
    """Scan every Python file in registry/ and evals/ for calls that pass
    sample_advice=. Only the seed setup may do this."""
    callers = set()
    for folder in ("registry", "evals"):
        for path in (PROJECT_ROOT / folder).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and any(
                        k.arg == "sample_advice" for k in node.keywords):
                    callers.add(path.name)
    assert callers == {"seed.py"}


# --- the refresh script ------------------------------------------------------------------

def test_refresh_writes_fresh_advice_with_current_model_and_fingerprint(tmp_path, fake_ai):
    out = tmp_path / "sample_advice.json"
    assert refresh(out, client=object()) is True
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["model"] == agent.load_config()["model"]
    assert data["instructions_fingerprint"] == agent.instructions_fingerprint()
    assert set(data["advice"]) == SEEDED_NAMES
    assert all(len(e["tool_fingerprint"]) == 64 for e in data["advice"].values())
    assert len(fake_ai.calls) == 3
    assert sample_advice.staleness_problems(data) == []


def test_refresh_keeps_old_file_if_any_ai_call_fails(tmp_path, fake_ai):
    out = tmp_path / "sample_advice.json"
    out.write_text('{"old": true}', encoding="utf-8")
    fake_ai.verdict = "needs_human"
    assert refresh(out, client=object()) is False
    assert json.loads(out.read_text(encoding="utf-8")) == {"old": True}


# --- older databases get the new column --------------------------------------------------

def test_older_database_gets_the_is_sample_column(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE ai_reviews (id INTEGER PRIMARY KEY, tool_id INTEGER, "
                "verdict TEXT, issues TEXT, reason TEXT, model TEXT, input_tokens INTEGER, "
                "output_tokens INTEGER, cost_usd REAL, response_seconds REAL, error TEXT, "
                "reviewed_at TEXT)")
    old.commit()
    old.close()
    conn = connect(str(path))
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(ai_reviews)")}
    conn.close()
    assert "is_sample" in columns
