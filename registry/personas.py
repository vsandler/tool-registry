"""The five personas (BRIEF.md "Users"). All names and emails are invented.

There is no real sign-in (DECISIONS.md #3): the person picks a persona.
"""

import sqlite3

ROLES = ("builder", "practice_admin", "super_admin", "specialist_reviewer", "tool_user")
ADMIN_ROLES = ("practice_admin", "super_admin")

# Specialist reviewer areas. "technology" is the AI enablement team.
SPECIALIST_AREAS = {
    "technology": "AI enablement (technology)",
    "compliance": "Compliance",
    "marketing": "Marketing",
}

PERSONAS = [
    {"id": "u-builder", "name": "Avery Quill", "email": "avery.quill@example.com",
     "role": "builder", "practice": "Tax", "specialty": None},
    {"id": "u-practice-admin", "name": "Morgan Fennel", "email": "morgan.fennel@example.com",
     "role": "practice_admin", "practice": "Tax", "specialty": None},
    {"id": "u-super-admin", "name": "Riley Ashgrove", "email": "riley.ashgrove@example.com",
     "role": "super_admin", "practice": None, "specialty": None},
    {"id": "u-specialist", "name": "Sam Thistle", "email": "sam.thistle@example.com",
     "role": "specialist_reviewer", "practice": None, "specialty": "compliance"},
    {"id": "u-specialist-tech", "name": "Devon Marsh", "email": "devon.marsh@example.com",
     "role": "specialist_reviewer", "practice": None, "specialty": "technology"},
    {"id": "u-specialist-marketing", "name": "Quinn Harrow", "email": "quinn.harrow@example.com",
     "role": "specialist_reviewer", "practice": None, "specialty": "marketing"},
    {"id": "u-tool-user", "name": "Jamie Larkspur", "email": "jamie.larkspur@example.com",
     "role": "tool_user", "practice": "Audit", "specialty": None},
]


def seed_personas(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO users (id, name, email, role, practice, specialty) "
        "VALUES (:id, :name, :email, :role, :practice, :specialty)",
        PERSONAS,
    )
    conn.commit()


def get_user(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def is_admin(user: sqlite3.Row) -> bool:
    return user["role"] in ADMIN_ROLES
