# Learning Log

_New concepts met while building, explained in plain language._

---

## Phase 7: Back end

### Storing data in SQLite
SQLite is a database that lives in a single file on your computer. There's no separate server to install or run. Python has it built in. We store users, tools, check results and approvals in tables, which work like spreadsheet tabs with fixed columns.

### Letting the database enforce rules
Some rules are written into the table definitions, so the database refuses bad data even if the code has a bug. For example, a user's role must be one of the five persona roles, and a tool's visibility must be `practice-only` or `firm-wide`. Anything else is turned away.

### Templates with fill-in-the-blank variables
A tool is stored as a template with blanks written like `{{client_name}}`. The stored template stays clean, with no client data in it. Each user fills in the blanks for their own copy. The code finds the blanks using a pattern-matching rule (a regular expression) and refuses to produce a copy if any blank is left unfilled.

### Throwaway test databases
Each test gets a brand-new database that exists only in memory and vanishes when the test ends. Tests can't affect each other, and nothing is left on disk.
