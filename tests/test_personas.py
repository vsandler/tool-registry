import sqlite3

import pytest

from registry.personas import ROLES, get_user, is_admin


def test_five_personas_one_per_role(conn):
    roles = [r["role"] for r in conn.execute("SELECT role FROM users")]
    assert sorted(roles) == sorted(ROLES)


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
