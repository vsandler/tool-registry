# Tool Registry

A governed catalogue of reusable AI tool templates: review once, reuse many times. See BRIEF.md for the problem and goals, and DECISIONS.md for key choices.

**Demo only.** All people, clients and numbers are made up. There's no real sign-in: you pick a persona.

## Run the back end

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn registry.api:create_app --factory --reload
```

Open http://127.0.0.1:8000/docs for a clickable list of every endpoint. On first run it creates `registry.db` with sample data, including one deliberately failing submission. Delete `registry.db` to start fresh.

Every request (except `/personas` and `/approval-steps`) needs an `X-Persona` header, for example `X-Persona: u-super-admin`.

## Run a demo

On first run, the sample data loads with no AI calls and no API key needed:

- **Three submitted tools** ("Meeting summary", "Engagement letter draft" and the deliberately failing "Client welcome letter") are already in the admin review queue. Their AI advice is **sample advice**: pre-written and copied from a real AI review, marked `"sample": true` with a label saying no AI call was made.
- **Two drafts for live demos**, owned by `u-builder` and not yet submitted:
  - **"Savings check-in note"**: subtly risky. It quietly promises savings "will steadily grow faster than inflation every year". It passes all six rule-based checks, so any flag comes from the AI.
  - **"Call notes tidy-up"**: clean and safe.

To demo the AI live, submit one of the drafts as `u-builder` (`POST /tools/{id}/submit`, with `GET /my-tools` to find the id). That makes a real AI call, so it needs an API key in `.env`, and the advice appears under `ai_review` in the response and in `GET /admin/review-queue`. Real submissions always call the AI.

### Refresh the sample advice

The sample advice records which model and which version of the agent's instructions produced it, plus a fingerprint of each seeded tool's content. If any of these changes (including an edit to a seeded tool in `registry/seed.py`), a test (`tests/test_sample_advice.py`) fails and explains what to do. To refresh it by hand:

```bash
.venv/Scripts/python -m registry.refresh_sample_advice
```

This makes 3 real AI calls (well under 1 cent) and rewrites `registry/sample_advice.json`. If any call fails, nothing is written. It never runs automatically. Read the new advice, run the tests and commit the file. Delete `registry.db` to reload the sample data with the new advice.

## Run the tests

```bash
.venv/Scripts/python -m pytest
```

## Approval flow

1. **Super admin** routes the tool to one or more specialist areas, in order: AI enablement (technology), compliance and/or marketing. Each chosen area becomes its own review step.
2. **Each specialist**, in that order, approves (a rejection at any step ends the review). A rejection needs a comment of at least 10 characters, and the tool then shows who rejected it, when, at which step and why.
3. **Super admin** sets visibility (practice-only or firm-wide) and publishes.

Nobody approves a tool they own, admins included. Each specialist must be a different person from whoever decided the other steps. Each tool's detail includes `steps`: every approval step, marked done, waiting, rejected or not reached, with who and when. Specialist reviewers can open the Review queue, which shows only the tools waiting for their area.

## What I'd build next

These match the To Do list in BACKLOG.md, which has the steps for each one.

- **Configurable approval order:** let a Super admin add, remove and reorder approval steps.
- **Hub-and-spoke routing (partly done):** tools can already go through several specialists in an order picked up front. What's left is letting the Super admin add the next specialist after seeing each review.
- **Reassign orphaned tools:** an admin hands a departed owner's tool to a current user.
- **Fix and resubmit after rejection:** a builder edits a rejected tool and sends it back for review.
- **Make the eval set harder:** the eval scored 17/17 risky and 16/16 safe in all 3 runs, so it may be too easy to show where the agent fails. Next: trick cases written by a second AI that hasn't seen the agent's instructions, and cases from real reviewer disagreements.
- **Model cascade:** the cheaper model reviews every submission, and anything it flags or is unsure about goes to a stronger model for a second opinion. Only worth building once a harder eval set shows the cheaper model missing things.
- **Parallel approvals:** let the Super admin choose, per tool, whether specialist reviews happen in order or at the same time. In parallel mode the tool moves to publish only when every area has approved, and any rejection ends the review. Open questions: how the progress line shows steps happening at once, and what happens to an open review when another specialist rejects.
- **Browser tests (Playwright):** automated tests that click through the real pages as each persona. Skipped for now because the rules are tested in Python.
- **Move the front end to React:** switch when there are more than a handful of screens, shared pieces like the progress line are reused in many places, there's a lot of live-updating state, or several people work on the front end.
- **Notifications:** tell people by email or a chat tool such as Microsoft Teams when a tool reaches their step, with a link, and tell the builder when their tool is approved, rejected (with the reason) or published. Open questions: avoiding overload (for example a daily digest), reminders for tools waiting too long, and what happens if the notification service is down (the queue still works).
- **Ticketing integration:** when a tool reaches a specialist step, open a ticket in that reviewer's ticketing system (for example Jira or ServiceNow) that links back to the tool, and update the tool when the ticket is approved or rejected. Open questions: how decisions sync back, how no self-approval is enforced across both systems, and what happens if the ticketing system is down.
- **Full audit trail for a real firm:** never delete or overwrite AI reviews or approval decisions, show the full review history in the review screen, keep call logs for a set time, record who changed the sample advice and when, and keep sample and demo data in a separate environment from live records.
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo
