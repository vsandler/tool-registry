# Tool Registry

A governed catalogue of reusable AI tool templates: review once, reuse many times. See BRIEF.md for the problem and goals, and DECISIONS.md for key choices.

**Demo only.** All people, clients and numbers are made up. There's no real sign-in: you pick a persona.

## Run the back end

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn registry.api:create_app --factory --reload
```

Open **http://127.0.0.1:8000/** for the app: pick a persona from the "Viewing as" dropdown at the top, then use the Catalog, Submit a tool and Review queue pages (the Review queue link appears only for personas who can open it). The screens are plain HTML and JavaScript in `web/`, served by the same server, with no build step. They only ask the back end and show its answers; all rules stay in the back end. Open http://127.0.0.1:8000/docs for a clickable list of every endpoint. On first run it creates `registry.db` with sample data, including one deliberately failing submission. Delete `registry.db` to start fresh.

Every request (except `/personas` and `/approval-steps`) needs an `X-Persona` header, for example `X-Persona: u-super-admin`.

## Run a demo

On first run, the sample data loads with no AI calls and no API key needed:

- **Three submitted tools** ("Meeting summary", "Engagement letter draft" and the deliberately failing "Client welcome letter") are already in the admin review queue. Their AI advice is **sample advice**: pre-written and copied from a real AI review, marked `"sample": true` with a label saying no AI call was made.
- **Two drafts for live demos**, owned by `u-builder` and not yet submitted:
  - **"Savings check-in note"**: subtly risky. It quietly promises savings "will steadily grow faster than inflation every year". It passes all six rule-based checks, so any flag comes from the AI.
  - **"Call notes tidy-up"**: clean and safe.

To demo the AI live, either fill in the **Submit a tool** page as Avery Quill (you can copy one of the drafts' text), or submit one of the drafts as `u-builder` (`POST /tools/{id}/submit`, with `GET /my-tools` to find the id). That makes a real AI call, so it needs an API key in `.env`, and the advice appears under `ai_review` in the response and in `GET /admin/review-queue`. Real submissions always call the AI.

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

## Submitting a tool

The **Submit a tool** page (`POST /submissions`) checks the form, then saves the tool and sends it for review in one go. Builders, admins and specialists can submit; Tool users can't (they use the Catalog), and the page link is hidden for them.

- **Required:** a name, the template text, who can see it (firm-wide or practice-only) and a rationale ("Why did you build it this way?"). If any is empty, nothing is saved and the back end says what's missing, box by box, so the page shows each message next to its box. The same rule applies to `POST /tools/{id}/submit`: a draft can be saved without a rationale, but can't be submitted until it has one.
- **Flags never block:** after that, the six rule-based checks and the AI pre-review run. A flagged tool still goes into review. The builder sees a confirmation, then each rule flag in plain words with a tip for next time, and the AI advice, kept separate.
- A rationale that's there but too short (under 20 characters, such as "n/a") is accepted and flagged by the `has_rationale` check.
- The sample "Client welcome letter" still has no rationale: it stands for a submission made before this rule (DECISIONS.md #15).

## Reviewing a tool

The **Review queue** page is for the Super admin, Practice admins and Specialist reviewers:

- **Two views:** "Waiting on me" (tools whose current step you can decide) and "All in review" (every tool you're allowed to see), oldest submitted first.
- **Picking a tool** shows its progress line, the template and rationale, the **rule flags** and the **AI advice** (kept separate: the advice never decides), and the history.
- **Your decision** appears only when it's your turn. Otherwise the page says why, for example "Waiting for a Compliance specialist." or "You built this tool, so you can't approve or reject it."
  - **Routing:** select the specialist areas in the order they should review, numbered 1, 2, 3.
  - **Publishing:** choose the visibility (and practice), starting from what the builder asked for. "This is the final approval. Approving publishes the tool."
  - **Rejecting:** needs a comment of at least 10 characters, which the builder will see.
- **Every rule is in the back end.** The page shows the choices it's given and the back end's own message for any refusal, next to the box or buttons it's about.

## Approval flow

1. **Super admin** routes the tool to one or more specialist areas, in order: AI enablement (technology), compliance and/or marketing. Each chosen area becomes its own review step.
2. **Each specialist**, in that order, approves (a rejection at any step ends the review). A rejection needs a comment of at least 10 characters, and the tool then shows who rejected it, when, at which step and why.
3. **Super admin** sets visibility (practice-only or firm-wide) and publishes.

Nobody approves a tool they own, admins included. Each specialist must be a different person from whoever decided the other steps. Each tool's detail includes `steps`: every approval step, marked done, waiting, rejected or not reached, with who and when. Specialist reviewers can open the Review queue, which shows only the tools waiting for their area, oldest submitted first. They can open a tool's details only while it waits for their area's review or after they've decided a step of it (least privilege). Practice admins see only their own practice's tools (a tool belongs to its owner's practice); the Super admin sees every tool. Each tool's detail also includes `my_action` for the persona asking: whether they can decide the current step, and if not, a plain reason why.

## What I'd build next

These match the To Do list in BACKLOG.md, which has the steps for each one.

- **Design polish (next, before the README screenshots):** the progress line as one connected progress bar, with done steps clearly marked; and the Review queue's empty views lined up, with no "Pick a tool" hint when there's nothing to pick.
- **Configurable approval order:** let a Super admin add, remove and reorder approval steps.
- **Hub-and-spoke routing (partly done):** tools can already go through several specialists in an order picked up front. What's left is letting the Super admin add the next specialist after seeing each review.
- **Reassign orphaned tools:** an admin hands a departed owner's tool to a current user.
- **Fix and resubmit after rejection:** a builder edits a rejected tool and sends it back for review. The progress line's "Skipped: rejected at step N" then becomes "On hold: waiting for the builder to fix and resubmit".
- **Make the eval set harder:** the eval scored 17/17 risky and 16/16 safe in all 3 runs, so it may be too easy to show where the agent fails. Next: trick cases written by a second AI that hasn't seen the agent's instructions, and cases from real reviewer disagreements.
- **Model cascade:** the cheaper model reviews every submission, and anything it flags or is unsure about goes to a stronger model for a second opinion. Only worth building once a harder eval set shows the cheaper model missing things.
- **Parallel approvals:** let the Super admin choose, per tool, whether specialist reviews happen in order or at the same time. In parallel mode the tool moves to publish only when every area has approved, and any rejection ends the review. Open questions: how the progress line shows steps happening at once, and what happens to an open review when another specialist rejects.
- **Browser tests (Playwright):** automated tests that click through the real pages as each persona. Skipped for now because the rules are tested in Python.
- **Move the front end to React:** switch when there are more than a handful of screens, shared pieces like the progress line are reused in many places, there's a lot of live-updating state, or several people work on the front end.
- **Update a published tool:** the builder submits a change as a new version that goes through the full review again, with no self-approval, while the current version stays in the catalogue until the new one is approved. Every version is kept, showing who changed what. Each tool gets its own never-edited decision log (part of the audit trail): what changed, why, who approved or rejected it at each step, and when. Builders see it for their own tools, approvers see it all, and tool users see only a short "what changed" note per version. When personalising, tool users see a "Why it's built this way" note with the key decisions and conditions (for example, "The disclaimer must stay: required by compliance"), never reviewers' internal comments. Open questions: whether small wording changes need the full review, and what happens to people's existing copies.
- **Practice versions:** a practice adapts a published tool, with review routed by what the change touches. Template values or wording need no specialist review. A new data source needs technology review, plus compliance if the data reaches clients. Client-facing or locked parts (such as a required disclaimer) go to the specialist who owns them. The practice admin reviews every practice version, with no self-approval, and each version links to the original and its decision log. Open questions: whether scope changes need review, and which small changes (such as an office address) need a specialist, to confirm with each specialist area.
- **Fill blanks from an approved data source:** a tool's blanks are filled automatically from a firm-approved data source that already filters by permission. The registry asks the source as the person using the tool, with their own access, never through a shared account that sees everything, so the source's permission rules always apply. Only sources on an approved list can be used. A tool can be approved with more than one source (for example, two market data providers), and the person using it picks which one to fill from, with no new review. Adding a source the tool wasn't approved for goes back through technology review (and compliance if the data reaches clients), as in "Practice versions". The downloaded copy notes which source was used. Filled values are never saved in the registry and never sent to the AI reviewer. Open questions: what happens if the source is down or returns nothing; whether people can edit a filled value before downloading; who sets and reviews each source's mapping to the tool's blanks, since sources name fields differently (for example "ticker" versus "symbol"); and whether one copy can mix sources or uses one source per copy.
- **Admin-managed practice list:** practices come from a list that admins keep, and the Submit form's "My practice isn't listed" asks an admin to add one. Builders never type their own practice, to avoid duplicates such as "Tax" and "Tax team". Open questions: who approves requests, what the builder does while waiting, what happens to tools when a practice is renamed or merged, and whether requests use notifications.
- **Notifications:** tell people by email or a chat tool such as Microsoft Teams when a tool reaches their step, with a link, and tell the builder when their tool is approved, rejected (with the reason) or published. Open questions: avoiding overload (for example a daily digest), reminders for tools waiting too long, and what happens if the notification service is down (the queue still works).
- **Approved outside the registry:** only the Super admin can mark a step approved elsewhere (for example in a ticket), recording who approved it, when and a reference. It's shown, labelled, in the history, and with ticketing integration the reference links to the ticket.
- **Let anyone propose a tool:** today Tool users can't submit. Later anyone could, and whoever submits becomes the tool's builder, with the same rules (no approving their own tool).
- **Ticketing integration:** when a tool reaches a specialist step, open a ticket in that reviewer's ticketing system (for example Jira or ServiceNow) that links back to the tool, and update the tool when the ticket is approved or rejected. Open questions: how decisions sync back, how no self-approval is enforced across both systems, and what happens if the ticketing system is down.
- **Full audit trail for a real firm:** never delete or overwrite AI reviews or approval decisions, show the full review history in the review screen, keep call logs for a set time, record who changed the sample advice and when, and keep sample and demo data in a separate environment from live records.
- **Real sign-in instead of the persona dropdown:** people sign in and their role comes from the firm's directory, so nobody picks a persona. Messages that say "pick a different persona" change, for example to "Ask an admin if you need access."
- **Spot overlap:** practices see a short summary of tools other practices are building (name, purpose, practice, status and contact person) to spot duplicates and team up, while rule flags, AI advice and reviewer comments stay private to that practice and its reviewers. Practice admins and the Super admin see the summary too, with a "Looks similar" flag in their queue when a tool resembles one another practice is building, so they can connect the builders. Linked to least privilege.
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo
