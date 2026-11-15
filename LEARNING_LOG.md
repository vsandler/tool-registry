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

### Rule-based checks that flag, never reject
When a tool is submitted, six simple rules run on it. Each rule gives a pass or a flag with a plain message, and the results are saved. A flagged tool still goes into review with its flags attached, so a person makes the final call. This follows the brief: "Anything flagged goes to a human; nothing is auto-rejected." The six rules:
1. **Variables match:** every blank used is declared, and every declared blank is used.
2. **No client data:** no email addresses, phone numbers or long account-style numbers.
3. **Rationale:** a short note on why the tool was built this way.
4. **Owner active:** the owner is still a current user, so no orphaned tools.
5. **Practice set:** a practice-only tool names its practice.
6. **Unique name:** flags a tool that already exists, to avoid building it twice.

### A deliberately failing example
The sample data includes one submission ("Client welcome letter") built to break four rules on purpose. A test checks that exactly those four are flagged. This proves the checks catch real problems, not just that they run.

### Testing many cases with one test
`@pytest.mark.parametrize` runs the same test several times with different inputs, such as an email, two phone formats and an account number. Each run counts as its own test.

### The approval order is data, not code
The approval steps are saved as a numbered list in a database table. Each step says which role approves it. The approval code reads that list and never names a role itself. Changing the order later, including the configurable order in the backlog, means changing the list, not rewriting the code. The tests use their own two-step list, so they check the rules without depending on what the real order turns out to be.

### Approval rules, and why they're checked in a set order
For each decision, the code checks in this order:
1. Is this your own tool? If so, refuse, whatever your role, admins included.
2. Is the tool actually in review?
3. Is it your role's turn?
4. Have you already decided a step of this tool?

The self-approval check comes first so an admin gets the clear reason ("you can't approve your own tool") rather than a confusing one. A refused attempt leaves no trace in the history.

### An approval history you only add to
Every decision becomes a new row: who, which step, approved or rejected, a comment and the time. Rows are never edited or deleted, so the history is a trustworthy record of how each tool got approved.

### Throwaway test databases
Each test gets a brand-new database that exists only in memory and vanishes when the test ends. Tests can't affect each other, and nothing is left on disk.
