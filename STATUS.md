# Status

## Current phase
Phase 8: AI pre-review agent (branch `phase-8-agent`, made from `phase-7-backend`). **8a, 8b and your four follow-ups are done and committed. Stopped before 8c, as asked.** Not pushed.

## New baseline score (run 2, 2026-11-15)
Model `claude-haiku-5-5`, effort `medium`. 33 made-up cases (17 risky, 16 safe), each run 3 times = 99 calls. Details in EVALS.md.

| Measure | Result | Target | Met? |
|---|---|---|---|
| Risky caught in every run | **17 / 17** | All | ✅ |
| Safe passed in every run | **16 / 16** (100% each run) | At least 80% (8 of 10) in every run | ✅ |
| Cost per review | avg $0.00020, max $0.00027 | Under 1 cent | ✅ |
| Response time | avg 1.49 s, max 2.55 s | Under 10 s | ✅ |

- **Missed cases:** none. No risky case slipped through in any run, and no safe case was flagged in any run.
- **Cases with different answers across runs:** none. All 33 cases got the same verdict all 3 times.
- **Failed replies (needs human):** 0 of 99.
- **Previous baseline (run 1):** 10/10 risky, 10/10 safe, 20 cases × 1 run.

I read the agent's issues for every new risky case, and each names the real problem, so these are right answers for the right reasons. Still, a perfect score on a set I wrote means it may be too easy to show where the agent fails. "Make the eval set harder" is now in BACKLOG.md and the README.

## Done
### Sample advice and audit trail (your answers of 2026-11-16)
- **No AI calls at startup.** The 3 seeded submissions show fixed sample advice from `registry/sample_advice.json`, marked `"sample": true` with a label. Real submissions always call the AI. Only the seed setup can pass sample advice: a test sends fake sample advice to the API's submit route and checks it's ignored, and another scans the code for any other caller.
- **Two demo drafts** for live demos: "Savings check-in note" (subtly risky: a soft promise about returns) and "Call notes tidy-up" (safe). Both pass all six rule-based checks. See the README's "Run a demo".
- **Staleness warning:** the sample advice stores the model, a fingerprint of the agent's instructions and a fingerprint of each seeded tool. `tests/test_sample_advice.py` fails with step-by-step instructions if any of them changes.
- **Manual refresh:** `.venv/Scripts/python -m registry.refresh_sample_advice`. It never runs automatically. I ran it once (3 calls, $0.00055) because the advice copied from the last real run had been made with the instructions from before the rationale split.
- **DECISIONS.md #6–#9** record this session's choices.
- **Backlog:** a full audit trail for a real firm, including a separate demo environment, added to BACKLOG.md and the README.
- **Tests:** 192 passing.

### Phase 8 follow-ups (your answers of 2026-11-15)
- **Agent runs on every submit, as advice only.** `submit_tool` runs the rule-based checks and then the AI. The AI's verdict, issues and reason are saved in a new `ai_reviews` table. They show under `ai_review` (marked `advice_only: true`) in tool details and the admin review queue. The AI never changes the status or the approval steps. If the AI fails in any way, the tool is still submitted and marked `needs_human`. The rule-based `flagged` field is unchanged, so the two kinds of flag stay apart.
- **Rationale check split.** The empty and "n/a" rationale cases moved from the AI eval set into the rule-based tests (`tests/test_checks.py`). The AI's instructions now say: judge whether a rationale that's present makes sense, and don't flag emptiness on its own. There are 3 new AI cases with long-enough but meaningless rationales (circular, filler, unrelated), and a test that keeps empty rationales out of the AI set.
- **12 harder cases + 3 runs each.** Subtle client data, soft return promises, disguised tricks, and 6 safe cases built to look risky. The eval script now runs every case 3 times and reports any case whose answer changes.
- **Backlog:** added "Make the eval set harder", and added a "What I'd build next" section to the README that mirrors the BACKLOG.md To Do list (the README didn't have one before).
- **Test changes (both explained in their commit messages):** the eval-set balance test now allows the risky and safe counts to differ by up to 2 (was exactly equal), to match "about half and half". The scoring tests were rewritten for multi-run results, keeping every old check.

### Phase 8a and 8b
- **8a: AI pre-review agent** (`registry/agent.py`). It reads the model and effort level from `config.json` and loads the API key from `.env` with python-dotenv. Our code never reads, prints or logs the key. It returns `risky` / `safe` + issues + reason, checked against a strict schema. Any bad, missing, refused or failed reply becomes `needs_human`. The submission is sent as escaped JSON inside `<submission>` tags and treated as data. Every call logs tokens, cost, response time and outcome to `logs/` (git-ignored).
- **8b: Eval set and script** (`evals/`), with results in `evals/results/` and EVALS.md.
- **New packages** (pinned in requirements.txt): `anthropic` 2.8.0, `python-dotenv` 1.2.4, and `pydantic` 2.14.3 (already installed, now pinned).
- **Tests:** 171 passing. A fake AI is swapped in for every test automatically, so the test suite never calls the real API.

### Phase 7 (earlier)
- Database, personas, tools, six rule-based checks, seed data, the three-step approval flow, the FastAPI API with the read-only admin review queue. See git history and DECISIONS.md #1.

## In progress
- Nothing. Waiting for you before 8c.

## Blocked / questions for Vanessa

**1. 8d: what decides Haiku vs Sonnet if both score 100%?**
Haiku 5.5 didn't miss or waver on a single case, so Sonnet 5.5 can't beat it on accuracy with this set. If Sonnet also scores 100%, should cost and speed decide (which favours Haiku), or would you rather do the "make the eval set harder" backlog item first so the comparison means something?

**2. What is 8c?**
I've stopped before it as asked. When you're ready, tell me what it covers.

**✅ Answered on 2026-11-16:** Real API calls when the app first starts? Use fixed, labelled sample advice for the 3 seeded tools, with no AI calls at startup, plus two demo drafts. **Done** (DECISIONS.md #9).

**✅ Answered on 2026-11-15:**
1. Run the agent on every submit, shown to reviewers as advice only. **Done.**
2. Add about 10 harder cases and run each 3 times. **Done** (12 cases).
3. Compare with Sonnet 5.5 after the harder set, in 8d. **Not started**, waiting for 8d.
4. Split the rationale check between rules and the AI. **Done.**

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
