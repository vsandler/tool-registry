import sqlite3

import pytest

from registry.tools import ToolError, create_tool, find_variables, get_tool, render


def test_find_variables_in_order_without_repeats():
    t = "Hi {{client_name}}, your {{ report_type }} is ready. Bye {{client_name}}."
    assert find_variables(t) == ["client_name", "report_type"]


def test_render_fills_in_values():
    assert render("Dear {{name}}", {"name": "Pat Example"}) == "Dear Pat Example"


def test_render_refuses_missing_values():
    with pytest.raises(ToolError, match="report_type"):
        render("{{name}} {{report_type}}", {"name": "Pat"})


def test_create_tool_saves_draft_with_detected_variables(conn):
    tool_id = create_tool(
        conn, name="Meeting summary", template="Summarise the {{meeting_topic}} meeting.",
        owner_id="u-builder", visibility="firm-wide",
    )
    tool = get_tool(conn, tool_id)
    assert tool["status"] == "draft"
    assert tool["variables"] == ["meeting_topic"]
    assert tool["visibility"] == "firm-wide"


@pytest.mark.parametrize("visibility", ["practice-only", "firm-wide"])
def test_both_visibility_labels_accepted(conn, visibility):
    tool_id = create_tool(conn, name="T", template="x", owner_id="u-builder",
                          visibility=visibility, practice="Tax")
    assert get_tool(conn, tool_id)["visibility"] == visibility


def test_unknown_visibility_refused(conn):
    with pytest.raises(ToolError):
        create_tool(conn, name="T", template="x", owner_id="u-builder", visibility="secret")


def test_unknown_owner_refused_by_database(conn):
    # create_tool now refuses an unknown owner before the database is reached
    # (REVIEW.md finding 2, tests/test_review_fixes.py). The database's own check
    # stays as a second layer, so it's tested directly, skipping create_tool.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tools (name, description, template, variables, visibility, practice, "
            "owner_id, rationale, status, created_at) "
            "VALUES ('T', '', 'x', '[]', 'firm-wide', NULL, 'nobody', '', 'draft', 'now')")
