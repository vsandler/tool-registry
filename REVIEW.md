# Code review (Phase 10)

## What was reviewed
- **What:** the whole Tool Registry after Phase 9: the back end (`registry/`), the three screens (`web/`), the tests (`tests/`) and the AI pre-review agent with its evals (`evals/`).
- **Version:** branch `phase-9-frontend`, at the commit that adds this file. _(Fill in the commit id when the review starts.)_
- **Tool:** OpenAI Codex, given the prompt in [docs/codex-review-prompt.md](docs/codex-review-prompt.md). It was told only to read and report, not to change any files. _(Fill in the Codex version or model.)_
- **When:** _(fill in the date of the review)_. Prepared on 2026-11-18.
- **A second opinion:** Codex is a different AI from the one that wrote the code (Claude), so it's less likely to share the same blind spots. Claude's own findings are added after Codex's, so they don't steer its review. The **Found by** column says which is which.

## What it was asked to look for
Bugs; security issues; ways around the approval rules (self-approval, the wrong role or area deciding, skipping steps, Tool users submitting); prompt-injection risks in the AI pre-review; secrets handling; and input validation.

**Known and on purpose (not findings):** the persona dropdown is a demo stand-in for real sign-in. Anyone can send any persona in the `X-Persona` header (DECISIONS.md #12; BACKLOG.md "Real sign-in"). All data is made up.

## Findings

**Severity:** Critical (breaks an approval rule or leaks secrets or client data), High (a real bug or security gap, but harder to reach), Medium (wrong behaviour in an edge case, or a weak check), Low (tidiness, clarity, small risk).

**Status:** Open, Fixed (with the commit), Won't fix (with the reason), Not a problem (checked; with the reason).

| # | Finding | Severity | Area | Found by | Fix | Status |
|---|---|---|---|---|---|---|
| | _None yet._ | | | | | |

**Area** is one of: Approval rules, Security, AI pre-review, Secrets, Input validation, Bug, Front end, Tests.

## How each finding is handled
1. Copy Codex's findings into the table as they are, with file and line in the Finding column.
2. Check each one: reproduce it with a test where possible, before fixing.
3. Fix in its own small commit, with a test that fails before the fix and passes after. Run the whole test suite.
4. Update the Fix and Status columns, and record any rule change in DECISIONS.md.

## Summary
_(To fill in after the review: how many findings by severity, how many fixed, and what was learned.)_
