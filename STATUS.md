# Status

## Current phase
Phase 8: AI pre-review agent (branch `phase-8-agent`, made from `phase-7-backend`). **8a and 8b are done and committed. Stopped before 8c, as asked.** Not pushed.

## Baseline score (8b, 2026-11-15)
Model `claude-haiku-5-5`, effort `medium`, 20 made-up submissions. Details in EVALS.md.

| Measure | Result | Target | Met? |
|---|---|---|---|
| Risky caught | 10 / 10 | All | ✅ |
| Safe passed | 10 / 10 | At least 8 / 10 | ✅ |
| Cost per review | avg $0.00019, max $0.00026 | Under 1 cent | ✅ |
| Response time | avg 1.73 s, max 2.89 s | Under 10 s | ✅ |

The agent caught the trick submission and named both tricks in it. Caution: the set is small, I wrote it, and it ran only once, so treat 10/10 as "handles the risks we thought of" rather than proof.

## Done
### Phase 8
- **8a: AI pre-review agent** (`registry/agent.py`). It reads the model and effort level from `config.json` and loads the API key from `.env` with python-dotenv. Our code never reads, prints or logs the key. It returns `risky` / `safe` + issues + reason, checked against a strict schema. Any bad, missing, refused or failed reply becomes `needs_human` (flagged for a person). The submission is sent as escaped JSON inside `<submission>` tags and treated as data. Every call is logged to `logs/agent_calls.jsonl` (git-ignored) with tokens, cost, response time and outcome. 31 new tests use a fake client, so the test suite never calls the real API.
- **8b: Eval set and script.** `evals/submissions.json` (10 risky, 10 safe, all made up), `evals/run_eval.py`, baseline results in `evals/results/` and EVALS.md. 8 new tests check the set itself and the scoring.
- **Tests:** 149 passing (110 from phase 7 + 39 new).
- **New packages** (in `.venv`, pinned in requirements.txt): `anthropic` 2.8.0, `python-dotenv` 1.2.4. `pydantic` 2.14.3 was already installed with FastAPI and is now pinned too because the agent uses it directly.
- **config.json** now also holds `"effort": "medium"` (how hard the model thinks). Medium is Haiku 5.5's default. I made it explicit so it can be tuned.

### Phase 7 (earlier)
- Database, personas, tools, six rule-based checks, seed data, the three-step approval flow, the FastAPI API with the read-only admin review queue. See git history and DECISIONS.md #1.

## In progress
- Nothing. Waiting for you before 8c.

## Blocked / questions for Vanessa

**1. Should the agent run automatically on submit?**
For now the agent is a standalone function (`review_tool`). It isn't wired into `submit_tool` or the API yet, because I didn't want to guess at 8c. Options: (A) run it on every submit and show its verdict and issues next to the rule-based flags in the review queue; (B) an admin presses a button to run it; (C) leave wiring for 8c. If it runs on submit, a failed AI call would just add a "needs human" flag. It would never block the submission.

**2. Make the eval harder?**
10/10 on both sides suggests the set is too easy to tell versions apart. That matters for DECISIONS.md #4 (Haiku 5.5 vs Sonnet 5.5). I'd suggest adding about 10 trickier cases: subtle promises ("comfortably beat inflation"), a lone real-looking name, a polite injection hidden in a variable name, and safe tools that use words like "guarantee" correctly. I could also run each case 3 times to check the results are consistent. Each full run costs under half a cent on Haiku.

**3. Compare against Sonnet 5.5 now?**
DECISIONS.md #4 says to run both models on the same evals before committing. Changing `config.json` is a one-line change, and a Sonnet run would cost about $0.08. Should I do this before or after making the set harder?

**4. Is "missing rationale" really *risky*?**
I labelled empty or meaningless rationales as risky, and the agent agrees. The rule-based `has_rationale` check already flags short ones. Are you happy for the AI to flag these as well, or should the AI focus on content risks?

_Earlier questions, both answered on 2026-11-14:_

**1. ✅ Answered: Who decides each step of the fixed approval order?**
Answer: three steps. (1) The Super admin routes the tool to one specialist area (AI enablement/technology, compliance, or marketing). (2) That specialist approves. (3) It returns to the Super admin, who sets visibility and publishes. The same Super admin may do steps 1 and 3, the specialist must be a different person, and there's no self-approval. Recorded in DECISIONS.md #1.

_Original question:_
DECISIONS.md #1 says "AI enablement approves first, then one other approver." But "AI enablement" isn't one of the five personas (Builder, Practice admin, Super admin, Specialist reviewer, Tool user), and "one other approver" doesn't say which role. Options:
- **A.** Step 1 AI enablement = **Super admin**. Step 2 = **Practice admin** for practice-only tools, **Specialist reviewer** for firm-wide tools. This uses the visibility label to pick step 2.
- **B.** Step 1 = **Super admin**. Step 2 = **Specialist reviewer**, always.
- **C.** Step 1 = **Super admin**. Step 2 = **Practice admin**, always.
- **D.** Add "AI enablement" as a sixth persona. This changes "five personas", so I haven't done it.

Whichever you pick, it's a one-line change. The engine already reads the order from a list, and option A only needs a small addition so step 2 can depend on the visibility label.

**2. ✅ Answered: What should the admin route do?**
Answer: the read-only review queue, as proposed. Reassigning orphaned tools is now in BACKLOG.md.

_Original question:_
My proposal: `GET /admin/review-queue`, which only Practice and Super admins can open. It would show every tool in review with its flags, its current step and its approval history. It would be read-only, so admins can't override or skip steps through it (no self-approval still applies). Is that what you had in mind, or should admins be able to do something more, such as reassign an orphaned tool to a new owner?

**✅ Assumptions confirmed by Vanessa:**
- Any persona can create and submit a tool. Only the tool's owner can submit it.
- The same Super admin may decide steps 1 and 3. The specialist (step 2) must be a different person from whoever decided any other step. Nobody approves or rejects a tool they own, admins included. _(This replaces my earlier "one person can't decide two steps" assumption.)_
- A rejection is final for now. There's no "fix and resubmit" yet.
- For the API, I plan to use FastAPI (a common, beginner-friendly Python web framework), installed into `.venv`.
