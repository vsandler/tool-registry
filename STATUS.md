# Status

## Current phase
Phase 7: Back end (branch `phase-7-backend`). Built and tested. Ready for your review. Not pushed.

## Done
- Set up permissions for autonomous building (.claude/settings.local.json)
- Created Python virtual environment (.venv) and ignored it in git
- Created branch phase-7-backend
- **Database and personas:** SQLite tables and the five made-up persona roles (all `@example.com`). There are 7 people in total, because there's one specialist for each of the three areas.
- **Tools:** templates with `{{variables}}` and a visibility label (`practice-only` / `firm-wide`)
- **Rule-based checks (6):** variables match, no client data, rationale, owner active, practice set, unique name. They flag only and never auto-reject.
- **Seed data:** two safe tools and one deliberately failing submission ("Client welcome letter"), which trips 4 checks
- **Approval flow (DECISIONS.md #1):** stored as a list of 3 steps: route (Super admin), specialist review (routed area only, different person), publish (Super admin sets visibility). The same Super admin may do steps 1 and 3. No self-approval for anyone, admins included. Add-only approval history.
- **API (FastAPI):** personas, approval steps, catalogue (respects visibility), create/submit, decisions, history, personalise, and the read-only admin review queue
- **Tests:** 110 passing, covering every check, every approval rule (routing, the return to Super admin, setting visibility, self-approval by each admin type) and every endpoint
- **Real server check:** started the server and confirmed the review queue shows the failing submission as flagged

## In progress
- Nothing.

## Possible next steps (your call)
- Front end with the persona dropdown
- AI pre-review agent (DECISIONS.md #4)
- Backlog items: configurable order, hub-and-spoke routing, reassigning orphaned tools, fix and resubmit

## Blocked / questions for Vanessa

_No open questions right now. Earlier questions, both answered on 2026-11-14:_

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
