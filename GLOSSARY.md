# Glossary

_Terms used in this project, defined in plain language._

- **Back end:** The part of the app that stores data and applies rules, behind the screens people see.
- **Constraint (database):** A rule written into a table, such as "role must be one of these five", that the database itself enforces.
- **Fixture (pytest):** A reusable setup step for tests, such as "give me a fresh database with the five personas in it".
- **In-memory database:** A database kept only in the computer's working memory. It disappears when the program stops, which is ideal for tests.
- **Persona:** One of the five made-up user types (Builder, Practice admin, Super admin, Specialist reviewer, Tool user) you pick from a dropdown instead of signing in.
- **pytest:** The Python tool that runs our automated tests and reports which ones pass or fail.
- **SQLite:** A small database stored in a single file, built into Python. No server needed.
- **Table:** Where a database keeps one kind of thing (users, tools, and so on). Each row is one item, and each column is one piece of information about it.
- **Virtual environment (.venv):** A private copy of Python just for this project, so its add-on packages don't mix with the rest of the computer.
