import pytest

from registry.checks import (
    check_has_rationale,
    check_no_client_data,
    check_owner_active,
    check_practice_for_practice_only,
    check_unique_name,
    check_variables_match,
)
from registry.seed import seed
from registry.tools import ToolError, create_tool, get_tool, submit_tool


def make_tool(**overrides):
    """A clean tool as a plain dict, for testing one check at a time."""
    tool = dict(
        id=999, name="Clean tool", description="Does a thing.",
        template="Hello {{name}}", variables=["name"], visibility="firm-wide",
        practice=None, owner_id="u-builder",
        rationale="Kept short so it's easy to reuse.",
    )
    tool.update(overrides)
    return tool


# --- variables_match ---------------------------------------------------------

def test_variables_match_passes_when_declared_equals_used(conn):
    assert check_variables_match(make_tool(), conn).passed


def test_variables_match_flags_undeclared_variable(conn):
    r = check_variables_match(make_tool(template="{{name}} {{year}}"), conn)
    assert not r.passed and "year" in r.message


def test_variables_match_flags_declared_but_unused(conn):
    r = check_variables_match(make_tool(variables=["name", "extra"]), conn)
    assert not r.passed and "extra" in r.message


# --- no_client_data ----------------------------------------------------------

def test_no_client_data_passes_clean_template(conn):
    assert check_no_client_data(make_tool(), conn).passed


@pytest.mark.parametrize("pasted, kind", [
    ("Email casey.sample@example.com", "email"),
    ("Call (555) 010-0199", "phone"),
    ("Call 555-010-0199", "phone"),
    ("Account 12345678", "account"),
])
def test_no_client_data_flags_pasted_details(conn, pasted, kind):
    r = check_no_client_data(make_tool(template="Hello {{name}}. " + pasted), conn)
    assert not r.passed and kind in r.message


def test_no_client_data_also_scans_rationale(conn):
    r = check_no_client_data(make_tool(rationale="Built for casey.sample@example.com last year"), conn)
    assert not r.passed


def test_no_client_data_allows_short_numbers_like_years(conn):
    assert check_no_client_data(make_tool(template="Hello {{name}}, see you in 2027."), conn).passed


# --- has_rationale -----------------------------------------------------------

def test_has_rationale_passes(conn):
    assert check_has_rationale(make_tool(), conn).passed


@pytest.mark.parametrize("rationale", ["", "   ", "too short"])
def test_has_rationale_flags_missing_or_short(conn, rationale):
    assert not check_has_rationale(make_tool(rationale=rationale), conn).passed


# The flag's message says what's wrong; its tip (CHECK_TIPS) says how to fix it.
@pytest.mark.parametrize("rationale", ["n/a", "too short", "  N/A  "])
def test_has_rationale_message_says_it_is_too_short(conn, rationale):
    r = check_has_rationale(make_tool(rationale=rationale), conn)
    assert r.message == "The reason is too short (under 20 characters)."


@pytest.mark.parametrize("rationale", ["", "   "])
def test_has_rationale_message_says_none_is_recorded(conn, rationale):
    """An empty rationale can't be submitted any more (DECISIONS.md #15), but the seeded
    sample tool and old drafts can still have one, so it gets its own message."""
    r = check_has_rationale(make_tool(rationale=rationale), conn)
    assert r.message == "No reason is recorded."


def test_has_rationale_tip_says_how_to_fix_without_repeating_the_message():
    from registry.checks import CHECK_TIPS
    tip = CHECK_TIPS["has_rationale"]
    assert tip == ("Write a sentence or two on why the tool is built this way, "
                   "for example why these steps or this wording.")
    assert "20" not in tip and "too short" not in tip.lower()


# Moved here from the AI eval set (evals/submissions.json, formerly risky-05 and
# risky-06). Missing or empty rationales are the rule-based check's job; the AI only
# judges whether a rationale that is present makes sense.
MOVED_FROM_AI_EVAL = {
    "empty rationale": dict(
        name="Meeting agenda builder",
        description="Builds an agenda for a client meeting.",
        template="Create a meeting agenda for {{client_name}} covering {{topics}}. "
                 "Meeting length: {{minutes}} minutes.",
        variables=["client_name", "topics", "minutes"],
        rationale="",
    ),
    "'n/a' rationale": dict(
        name="Proposal cover note",
        description="Cover note for a written proposal.",
        template="Write a one-paragraph cover note for a proposal to {{client_name}} "
                 "about {{service}}.",
        variables=["client_name", "service"],
        rationale="n/a",
    ),
}


@pytest.mark.parametrize("case", MOVED_FROM_AI_EVAL)
def test_has_rationale_flags_cases_moved_from_ai_eval(conn, case):
    tool = make_tool(**MOVED_FROM_AI_EVAL[case])
    assert not check_has_rationale(tool, conn).passed


@pytest.mark.parametrize("case", MOVED_FROM_AI_EVAL)
def test_moved_cases_fail_only_the_rationale_check(conn, case):
    """Everything else about them is clean, so the rationale is the only thing caught."""
    from registry.checks import run_checks
    failed = [r.name for r in run_checks(conn, make_tool(**MOVED_FROM_AI_EVAL[case]))
              if not r.passed]
    assert failed == ["has_rationale"]


# --- owner_active ------------------------------------------------------------

def test_owner_active_passes_for_current_user(conn):
    assert check_owner_active(make_tool(), conn).passed


def test_owner_active_flags_departed_owner(conn):
    conn.execute("UPDATE users SET active = 0 WHERE id = 'u-builder'")
    assert not check_owner_active(make_tool(), conn).passed


# --- practice_set ------------------------------------------------------------

def test_practice_set_passes_for_firm_wide_without_practice(conn):
    assert check_practice_for_practice_only(make_tool(), conn).passed


def test_practice_set_passes_for_practice_only_with_practice(conn):
    tool = make_tool(visibility="practice-only", practice="Tax")
    assert check_practice_for_practice_only(tool, conn).passed


def test_practice_set_flags_practice_only_without_practice(conn):
    tool = make_tool(visibility="practice-only", practice=None)
    assert not check_practice_for_practice_only(tool, conn).passed


# --- unique_name -------------------------------------------------------------

def test_unique_name_passes_when_no_clash(conn):
    assert check_unique_name(make_tool(), conn).passed


def test_unique_name_flags_existing_tool_ignoring_case(conn):
    tid = create_tool(conn, name="Clean Tool", template="x", owner_id="u-builder",
                      visibility="firm-wide")
    conn.execute("UPDATE tools SET status = 'in_review' WHERE id = ?", (tid,))
    assert not check_unique_name(make_tool(name="  clean tool "), conn).passed


def test_unique_name_ignores_drafts(conn):
    create_tool(conn, name="Clean tool", template="x", owner_id="u-builder", visibility="firm-wide")
    assert check_unique_name(make_tool(), conn).passed


# --- submitting --------------------------------------------------------------

def test_submit_clean_tool_goes_to_review_unflagged(conn):
    tid = create_tool(conn, name="Clean tool", template="Hello {{name}}", owner_id="u-builder",
                      visibility="firm-wide", rationale="Kept short so it's easy to reuse.")
    result = submit_tool(conn, tid, "u-builder")
    assert result["flagged"] is False
    assert get_tool(conn, tid)["status"] == "in_review"


def test_only_owner_can_submit(conn):
    tid = create_tool(conn, name="T", template="x", owner_id="u-builder", visibility="firm-wide")
    with pytest.raises(ToolError, match="owner"):
        submit_tool(conn, tid, "u-practice-admin")


def test_cannot_submit_twice(conn):
    # A rationale is needed to submit at all (DECISIONS.md #15); this test is about the second try.
    tid = create_tool(conn, name="T", template="x", owner_id="u-builder", visibility="firm-wide",
                      rationale="Kept short so it's easy to reuse.")
    submit_tool(conn, tid, "u-builder")
    with pytest.raises(ToolError, match="drafts"):
        submit_tool(conn, tid, "u-builder")


# --- the seeded, deliberately failing submission ------------------------------

def test_seeded_failing_submission_is_flagged_but_not_rejected(conn):
    ids = seed(conn)
    bad = ids["Client welcome letter"]
    failed = {r["check_name"] for r in conn.execute(
        "SELECT check_name FROM check_results WHERE tool_id = ? AND passed = 0", (bad,))}
    assert failed == {"no_client_data", "variables_match", "has_rationale", "practice_set"}
    # Flagged goes to a human; nothing is auto-rejected.
    assert get_tool(conn, bad)["status"] == "in_review"


def test_seeded_safe_submissions_pass_every_check(conn):
    ids = seed(conn)
    for name in ("Meeting summary", "Engagement letter draft"):
        failed = conn.execute(
            "SELECT count(*) FROM check_results WHERE tool_id = ? AND passed = 0", (ids[name],)
        ).fetchone()[0]
        assert failed == 0, name
