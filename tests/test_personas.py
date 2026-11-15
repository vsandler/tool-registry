import sqlite3

import pytest

from registry.personas import ROLES, SPECIALIST_AREAS, get_user, is_admin


def test_all_five_persona_roles_present(conn):
    roles = {r["role"] for r in conn.execute("SELECT role FROM users")}
    assert roles == set(ROLES) and len(ROLES) == 5


def test_one_specialist_per_area(conn):
    areas = [r["specialty"] for r in conn.execute(
        "SELECT specialty FROM users WHERE role = 'specialist_reviewer'")]
    assert sorted(areas) == sorted(SPECIALIST_AREAS)


def test_persona_emails_are_made_up(conn):
    for row in conn.execute("SELECT email FROM users"):
        assert row["email"].endswith("@example.com")


def test_admin_roles(conn):
    assert is_admin(get_user(conn, "u-practice-admin"))
    assert is_admin(get_user(conn, "u-super-admin"))
    assert not is_admin(get_user(conn, "u-builder"))


def test_unknown_role_rejected_by_database(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (id, name, email, role) VALUES ('x', 'X', 'x@example.com', 'wizard')"
        )
