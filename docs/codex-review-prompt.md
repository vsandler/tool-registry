# Prompt for the Codex review (Phase 10)

Copy everything below the line into Codex, run from the project folder.

---

You are reviewing a small demo app called **Tool Registry**. It's a catalogue of AI prompt templates for a made-up professional-services firm. Builders submit templates, which go through a fixed approval flow, and the approved ones are published to a catalogue. It's Python (FastAPI and SQLite) with plain HTML and JavaScript screens. All people, clients and data in it are made up.

## Ground rules: read and report only
- **Do not change any files.** Don't edit, create, rename or delete anything, don't commit, and don't install packages. Report your findings in your reply only.
- **Don't open `.env` or any `.env.*` file**, and don't print environment variables. They may hold a real API key. If a finding is about secrets, describe it from the code that reads them (`registry/agent.py`), not from the secret itself.
- **Make no network calls or real AI calls.** Don't run `evals/run_eval.py` or `registry/refresh_sample_advice.py`: they call a paid API.
- **You may run the tests** to check an idea, with `.venv/Scripts/python -m pytest -q -p no:cacheprovider`, so nothing is written. The tests use an in-memory database and a fake AI.

## How it's meant to work
Check the code against these rules. The reasons are in `DECISIONS.md`; the vocabulary is in `GLOSSARY.md`.

- **Personas.** There's no real sign-in: the `X-Persona` header picks a made-up person. This is on purpose for the demo, so don't report "anyone can pretend to be anyone" as a finding. Do report it if the back end trusts anything else the browser sends: a role, an owner, an area, or a step.
- **Roles:** Builder, Practice admin, Super admin, Specialist reviewer (each with one area: AI enablement (technology), Compliance or Marketing), and Tool user. The roles are defined in `registry/personas.py`.
- **Who can submit:** everyone except Tool users. Tool users only use published tools, and are refused on the Submit form, on saving a draft and on submitting.
- **The approval flow, in order, with no skipping:**
  1. **Route:** the Super admin routes the tool to one or more specialist areas, in an order they choose.
  2. **Review:** one step per routed area, decided by a Specialist reviewer from that area.
  3. **Publish:** the Super admin publishes it as Firm-wide or Practice-only, which needs a practice.
- **No self-approval:** nobody approves or rejects a tool they own, admins included.
- **Different person:** each specialist review must be decided by someone who hasn't decided any other step of that tool. The same Super admin may do Route and Publish.
- **Rejections:** a rejection at any step ends the review, and needs a comment of at least 10 characters.
- **Decisions can't be removed or changed:** they are only ever added.
- **Least privilege:** a Practice admin sees only their own practice's tools in review. A Specialist sees only tools waiting for their area. People see only the published tools they may use: firm-wide, or practice-only for their own practice.
- **The AI pre-review** (`registry/agent.py`) is advice only. It never approves, rejects or blocks a tool. The submission is untrusted data. Any bad, missing or failed AI reply becomes "needs a human".
- **Rule-based checks** (`registry/checks.py`) flag problems, such as client data in a template, but never block a submission.
- **The screens only display.** Every rule lives in the back end. The pages show what the API says (for example `my_action.can_decide`) and put text on screen as text, never as HTML.

## What to review
Look across the whole project. Start with these files, which hold most of the rules:
1. `registry/approvals.py`: who may decide which step, in what order, and what a decision records.
2. `registry/api.py`: every web address (endpoint), what each one checks, and what data it returns to whom.
3. `registry/tools.py`: creating, submitting and personalising tools, the Tool-user refusal and input checks.
4. `registry/agent.py`: the AI pre-review: prompt, wrapping the submission, checking the reply, the API key, logging.
5. `registry/personas.py`: the roles and which roles may submit or open the Review queue.

Then `registry/checks.py`, `registry/db.py`, `registry/seed.py`, `web/app.js`, `web/queue.html`, `web/submit.html`, `web/index.html`, and the tests.

Look for:
1. **Bugs:** wrong results, crashes, or edge cases that aren't handled (empty values, very long text, unusual characters, two requests at once).
2. **Security issues:** for example data shown to someone who shouldn't see it, text that could run as page code (cross-site scripting), unsafe database queries, files served that shouldn't be, or error messages that give away internals.
3. **Ways around the approval rules:**
   - **Self-approval:** anyone deciding a tool they own, by any route.
   - **Wrong role or area:** a Specialist deciding another area's review, or a non-admin routing or publishing.
   - **Skipping steps:** deciding out of order, deciding twice, deciding after a rejection or after publishing, or changing the route after it's set.
   - **Tool users submitting:** by any endpoint, including saving a draft first and submitting later.
   - **Different person:** the same person deciding two specialist reviews of one tool.
   - **Seeing more than allowed:** another practice's tools, rule flags, AI advice or reviewer comments.
4. **Prompt injection in the AI pre-review:** can a submission's text (name, description, template, rationale, practice) escape the `<submission>` wrapping, steer the AI's verdict, or change what's saved or shown? Remember the AI's advice is meant to be advice only. Also check whether anything the AI returns is trusted where it shouldn't be.
5. **Secrets handling:** how the API key is loaded, and whether it, or anything sensitive, could reach logs, error messages, API responses, the screens, test output or git (check `.gitignore`).
6. **Input validation:** what the API accepts that it shouldn't, such as unknown fields, wrong types, very long text, unknown practices or areas, repeated areas, or a visibility or practice that doesn't match the rules. Check both the back end's own checks and what FastAPI and Pydantic check.

## How to report
For each finding, give:
- **#**: a running number.
- **Finding:** one or two plain sentences on what's wrong and why it matters.
- **File and line:** for example `registry/approvals.py:254`.
- **Severity:** one of these:
  - **Critical:** breaks an approval rule, or leaks secrets or client data.
  - **High:** a real bug or security gap, but harder to reach.
  - **Medium:** wrong behaviour in an edge case, or a weak check.
  - **Low:** tidiness, clarity or small risk.
- **Area:** Approval rules, Security, AI pre-review, Secrets, Input validation, Bug, Front end, or Tests.
- **How to see it:** the steps or request that shows the problem, for example the persona, endpoint and body. Say if you checked it by running the tests or code, or only by reading.
- **Suggested fix:** what to change, in a sentence or two, and a test that would prove it's fixed. Don't apply it.

Put the findings in one Markdown table, most severe first, with these columns:
`| # | Finding | File:line | Severity | Area | How to see it | Suggested fix |`

After the table, add:
- **Checked and found fine:** the rules and areas you looked at closely and found no problem with, so the coverage is clear.
- **Not checked:** anything you couldn't review, and why.

Be specific and don't pad the list: one real, confirmed finding is worth more than several guesses. If you're not sure, say so and mark it as a question rather than a finding.
