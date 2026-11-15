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
