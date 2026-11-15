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
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo
