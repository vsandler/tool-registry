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

### The three-step flow: route, review, publish
Each step in the stored list now has an *action* as well as a role:
1. **Route:** the Super admin picks one specialist area (AI enablement/technology, compliance or marketing). The choice is saved on the tool.
2. **Review:** only a specialist from *that* area can decide this step. A marketing specialist can't approve a tool routed to compliance.
3. **Publish:** the tool comes back to the Super admin, who chooses its final visibility and publishes it.

Whatever is chosen (the area, or "published as firm-wide") is written into the history next to the decision.

### "Different person" is a setting on a step, not a blanket rule
The same Super admin is allowed to do steps 1 and 3. So instead of "nobody may decide two steps", the review step carries a `different_person` flag. Whoever decides it must not have decided any other step of that tool. No self-approval is separate and applies to every step and every role.

### Changing a test because the rule changed
The earlier test "the same person can't decide two steps" was replaced, not weakened. Vanessa's decision changed the rule itself, so the old test described behaviour we no longer want. New tests cover the new rule from both sides: the same Super admin *may* route and publish, and the specialist *must* be a different person.

### An API: a menu of requests the back end answers
The API is a list of web addresses (endpoints) that a front end, or a person using the `/docs` page, can call. For example, `POST /tools/5/decisions` means "record a decision on tool 5". FastAPI checks each request's shape (for example "decision must be text") before our code runs, and it builds the `/docs` page automatically.

### Saying who you are with a header
Instead of signing in, each request carries an `X-Persona` header naming the persona, which stands in for the dropdown. An unknown persona gets a 401 ("who are you?"). A known persona doing something they're not allowed to do gets a 403 ("not allowed").

### Status codes tell the front end what went wrong
- **200 / 201:** worked (201 = something new was created).
- **400:** your request is missing something or has a bad value. Fix it and try again.
- **401:** we don't know who you are.
- **403:** we know who you are, but you're not allowed (for example, approving your own tool).
- **404:** that tool doesn't exist.
- **405:** that kind of request isn't allowed here. This is how we prove the admin review queue is read-only.

Our errors are grouped into families (not found, not allowed, bad input), and each family maps to one code.

### A read-only admin route
`GET /admin/review-queue` shows admins every tool waiting for review, with its flags, current step and history. It only supports *reading*. There's no way to approve, skip or change anything through it, so it can't be used to get round the approval rules.

### Who sees what in the catalogue
Firm-wide published tools are visible to everyone. Practice-only published tools are visible only to people in that practice (and to Super admins). Unpublished tools never appear in the catalogue.

### Throwaway test databases
Each test gets a brand-new database that exists only in memory and vanishes when the test ends. Tests can't affect each other, and nothing is left on disk.
