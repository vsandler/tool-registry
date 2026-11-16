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

1. **Super admin** routes the tool to one specialist area: AI enablement (technology), compliance, or marketing.
2. **That specialist** approves.
3. **Super admin** sets visibility (practice-only or firm-wide) and publishes.

Nobody approves a tool they own, admins included. The specialist must be a different person from whoever decided the other steps.

## What I'd build next

These match the To Do list in BACKLOG.md, which has the steps for each one.

- **Configurable approval order:** let a Super admin add, remove and reorder approval steps.
- **Hub-and-spoke routing:** after each specialist review, the Super admin can send the tool to another specialist or publish it.
- **Reassign orphaned tools:** an admin hands a departed owner's tool to a current user.
- **Fix and resubmit after rejection:** a builder edits a rejected tool and sends it back for review.
- **Make the eval set harder:** the eval scored 17/17 risky and 16/16 safe in all 3 runs, so it may be too easy to show where the agent fails. Next: trick cases written by a second AI that hasn't seen the agent's instructions, and cases from real reviewer disagreements.
- **Full audit trail for a real firm:** never delete or overwrite AI reviews or approval decisions, show the full review history in the review screen, keep call logs for a set time, record who changed the sample advice and when, and keep sample and demo data in a separate environment from live records.
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo
