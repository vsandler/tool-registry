# Glossary

_Terms used in this project, defined in plain language._

- **Append-only:** A record you only add to. Old entries are never changed or removed. Our approval history works this way.
- **Approval history:** The list of every approve or reject decision on a tool: who made it, at which step, when, and any comment.
- **Approval step:** One stage in the approval order, naming the role that decides it, for example "step 1, decided by a Super admin".
- **Action (approval step):** What deciding a step does: `route` (send to a specialist area), `review` (specialist approves), or `publish` (set visibility and make it available).
- **Back end:** The part of the app that stores data and applies rules, behind the screens people see.
- **Constraint (database):** A rule written into a table, such as "role must be one of these five", that the database itself enforces.
- **Flag:** A warning attached to a submission when a check fails. It points a human reviewer at the problem but does not reject the tool.
- **Fixture (pytest):** A reusable setup step for tests, such as "give me a fresh database with the five personas in it".
- **In-memory database:** A database kept only in the computer's working memory. It disappears when the program stops, which is ideal for tests.
- **Persona:** One of the five made-up user types (Builder, Practice admin, Super admin, Specialist reviewer, Tool user) you pick from a dropdown instead of signing in.
- **pytest:** The Python tool that runs our automated tests and reports which ones pass or fail.
- **Orphaned tool:** A tool whose owner has left, so nobody looks after it.
- **Parametrize (pytest):** Running one test several times with different inputs.
- **Publish:** The last approval step. The Super admin sets the tool's visibility and it becomes available in the catalogue.
- **Rationale:** The short note kept with each tool explaining why it was built the way it was.
- **Regular expression (regex):** A compact pattern for finding text, such as "two curly braces, a name, two curly braces". We use them to find template variables and to spot things like email addresses.
- **Routing:** The Super admin sending a tool to one specialist area for review.
- **Rule-based check:** A fixed, simple test (no AI) run on every submission, such as "does the template contain an email address?".
- **Render:** Filling in a template's blanks with real values to produce a finished copy.
- **Self-approval:** Approving a tool you own. Never allowed, for any role, admins included.
- **Seed data:** Made-up sample records loaded into an empty database so there's something to work with.
- **SQLite:** A small database stored in a single file, built into Python. No server needed.
- **Specialist area:** One of the three review teams: AI enablement (technology), compliance, or marketing.
- **Submission:** A builder sending a draft tool in for review. The checks run at this moment.
- **Table:** Where a database keeps one kind of thing (users, tools, and so on). Each row is one item, and each column is one piece of information about it.
- **Template:** A tool's reusable text with blanks (template variables) for each user to fill in. Reviewed once, reused many times.
- **Template variable:** A named blank in a template, written `{{like_this}}`.
- **Virtual environment (.venv):** A private copy of Python just for this project, so its add-on packages don't mix with the rest of the computer.
- **Visibility label:** Each tool's setting for who can see it once approved: `practice-only` (one practice) or `firm-wide` (everyone).
