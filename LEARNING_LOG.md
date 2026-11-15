# Learning Log

_New concepts met while building, explained in plain language._

---

## Phase 7: Back end

### Storing data in SQLite
SQLite is a database that lives in a single file on your computer. There's no separate server to install or run. Python has it built in. We store users, tools, check results and approvals in tables, which work like spreadsheet tabs with fixed columns.

### Letting the database enforce rules
Some rules are written into the table definitions, so the database refuses bad data even if the code has a bug. For example, a user's role must be one of the five persona roles, and a tool's visibility must be `practice-only` or `firm-wide`. Anything else is turned away.

### Throwaway test databases
Each test gets a brand-new database that exists only in memory and vanishes when the test ends. Tests can't affect each other, and nothing is left on disk.
