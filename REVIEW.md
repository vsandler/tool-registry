# Code review (Phase 10)

## What was reviewed
- **What:** the whole Tool Registry after Phase 9: the back end (`registry/`), the three screens (`web/`), the tests (`tests/`) and the AI pre-review agent with its evals (`evals/`).
- **Version:** branch `phase-9-frontend`, at commit `b89a8f1` (the commit that adds this file).
- **Tool:** OpenAI Codex v0.169.0, model GPT-6-Luna, reasoning effort medium, with Read Only permissions. It was given the prompt in [docs/codex-review-prompt.md](docs/codex-review-prompt.md), and told only to read and report, not to change any files.
- **When:** reviewed on 2026-11-18. Prepared the same day.
- **A second opinion:** Codex is a different AI from the one that wrote the code (Claude), so it's less likely to share the same blind spots. Claude's own findings are added after Codex's, so they don't steer its review. The **Found by** column says which is which.

## What it was asked to look for
Bugs; security issues; ways around the approval rules (self-approval, the wrong role or area deciding, skipping steps, Tool users submitting); prompt-injection risks in the AI pre-review; secrets handling; and input validation.

**Known and on purpose (not findings):** the persona dropdown is a demo stand-in for real sign-in. Anyone can send any persona in the `X-Persona` header (DECISIONS.md #12; BACKLOG.md "Real sign-in"). All data is made up.

## Findings

**Severity:** Critical (breaks an approval rule or leaks secrets or client data), High (a real bug or security gap, but harder to reach), Medium (wrong behaviour in an edge case, or a weak check), Low (tidiness, clarity, small risk).

**Status:** Open, Fixed (with the commit), Won't fix (with the reason), Not a problem (checked; with the reason).

| # | Finding | Severity | Area | Found by | Fix | Status |
|---|---|---|---|---|---|---|
| 1 | Any non-empty practice name is accepted, both when creating a tool and when publishing it as Practice-only, so a typo such as "Txa" makes a practice nobody belongs to. `registry/tools.py:175-185`, `registry/approvals.py:462-466` | Medium | Input validation | Codex | Saving, submitting and publishing refuse a practice that isn't in the list ("Choose a practice from the list: Audit or Tax."). A blank one is still flagged, not refused. DECISIONS.md #22. | Fixed (`a03e6e3`) |
| 2 | `check_can_submit` lets an unknown user id through: it only refuses a known user whose role can't submit. The API refuses unknown personas first, so it isn't a live hole, but the guard is fragile if another way in is added. `registry/tools.py:200` | Low | Approval rules | Claude (missed by Codex) | `check_can_submit` refuses anyone not in the registry ("Only people in the registry can save or submit tools.") before any save, check or AI call. Before, a draft save crashed on the database's owner link instead. DECISIONS.md #22. | Fixed (`e14891d`) |
| 3 | No length limits on text fields (name, description, template, rationale, comments). A very long template is sent to the AI in full, so input tokens and cost per review are unbounded; `MAX_TOKENS` only caps the reply. `registry/tools.py:73`, `registry/approvals.py:444` | Medium | Input validation (cost) | Claude (missed by Codex) | Limits on every box (name 100, description 500, template 5,000, rationale 1,000 and decision comments 1,000 characters; up to 50 blanks), checked when saving, submitting and deciding, before anything reaches the AI. Worst case about $0.0013 per review. `registry/agent.py` unchanged. DECISIONS.md #22. | Fixed (`23a39ef`) |

**Area** is one of: Approval rules, Security, AI pre-review, Secrets, Input validation, Bug, Front end, Tests.

## The blind test
While preparing the prompt, Claude spotted 3 possible problems (findings 1–3). It held them back from the prompt and this table so Codex would review unsteered. Codex found 1 of the 3 on its own (finding 1, the practice name). It missed the unknown-user guard (finding 2) and the missing length limits (finding 3). Claude added those after Codex reported.

**What this shows:** a second AI reviewer adds a real check, but it didn't catch everything. Neither reviewer is a full guarantee, so each finding gets a test.

## How each finding is handled
1. Copy Codex's findings into the table as they are, with file and line in the Finding column.
2. Check each one: reproduce it with a test where possible, before fixing.
3. Fix in its own small commit, with a test that fails before the fix and passes after. Run the whole test suite.
4. Update the Fix and Status columns, and record any rule change in DECISIONS.md.

## Summary
- **Findings:** 3 in all: 2 Medium (the practice name, the missing length limits) and 1 Low (the unknown-user guard). No Critical or High.
- **Fixed:** all 3, one commit each, each with a test written first that failed before the fix. The test suite went from 523 to 558 passing.
- **Who found what:** Codex found 1 of the 3 on its own (finding 1). Claude had spotted all 3 beforehand and added findings 2 and 3 after Codex reported.
- **AI pre-review:** `registry/agent.py` was unchanged, so the eval results and sample advice still apply.
- **What was learned:** a second AI reviewer adds a real check, but it missed 2 of the 3 known problems. Neither reviewer is a guarantee, so every finding gets a test.
