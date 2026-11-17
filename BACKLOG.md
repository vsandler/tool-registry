# Backlog

## To Do
- **Configurable approval order**
  - **Why it was cut:** The back end couldn't be finished by Saturday evening, so the order is fixed for now: AI enablement, then one other approver. See DECISIONS.md #1.
  - **Steps to build it:**
    1. Add a settings screen where a Super admin can add, remove, and reorder approval steps.
    2. Save each order as an ordered list of steps (this is the same list format used today).
    3. Choose which order applies to a tool, for example based on its visibility label (practice-only or firm-wide).
    4. Update the approval flow so it reads the saved order instead of the fixed default.
    5. Keep the current fixed order as the default when nothing has been set up.
    6. Add tests: a custom order runs in the right sequence, and the default still works.
- **Hub-and-spoke routing (partly done)**
  - **What it is:** After each specialist approves, the tool returns to the Super admin. The Super admin can then send it to another specialist, as many times as needed, or publish it as practice-only or firm-wide.
  - **Already done by multi-specialist routing (DECISIONS.md #11):** a tool can have several specialist reviews, each its own step with its own history entry. The progress line shows every review. "Specialist must be a different person" and "no self-approval" apply at every step, and a rejection at any review ends it.
  - **What's left:** today the Super admin picks every area up front, in a fixed order. Hub-and-spoke would let them decide the next area **after seeing each review**.
  - **Steps to build it:**
    1. After each review, return the tool to the Super admin with two choices: add another specialist area, or move on to publishing.
    2. Append the new review step to the tool's own step list, so the history and progress line stay accurate.
    3. Stop the same area being added twice by mistake, or ask the Super admin to confirm it.
    4. Add tests: add an area after the first review, then publish; publish straight after one review; the new step still follows no self-approval and different person.
- **Reassign orphaned tools to a new owner**
  - **What it is:** When a tool's owner leaves, an admin hands the tool to a current user.
  - **Why it was cut:** The "owner active" check already flags orphaned tools, which was enough for the demo. Reassigning them needs its own admin action and history.
  - **Steps to build it:**
    1. Add an admin-only action that changes a tool's owner to an active user.
    2. Record each reassignment (old owner, new owner, who did it, when) in a history table.
    3. List orphaned tools in the admin review queue so admins can find them.
    4. Re-check self-approval after the change: the new owner can't approve the tool either.
    5. Add tests: only admins can reassign; the new owner must be active; history is recorded; the new owner can't self-approve.
- **Fix and resubmit after rejection**
  - **What it is:** A builder edits a rejected tool and sends it back for review.
  - **Why it was cut:** For now a rejection is final. That keeps the approval history and status rules simple for the weekend build.
  - **Steps to build it:**
    1. Let the owner turn a rejected tool back into a draft and edit it.
    2. Keep the earlier approval history and mark it as belonging to a previous round.
    3. Re-run the rule-based checks on resubmission.
    4. Start the approval order again from step 1.
    5. Add tests: only the owner can resubmit; checks re-run; old history is kept; the review restarts at step 1.
- **Make the eval set harder**
  - **Why it's needed:** The improved eval scored 17/17 risky and 16/16 safe in all 3 runs, so the test may be too easy to show where the agent fails. See EVALS.md.
  - **Steps to build it:**
    1. Ask a second AI (for example Codex) to write new made-up trick cases without seeing the agent's instructions.
    2. Add cases from real mistakes, once people use the tool: every time a human reviewer disagrees with the AI's advice, save it as a new eval case.
    3. Rerun the eval and record the new score in EVALS.md.
- **Model cascade**
  - **What it is:** The cheaper model reviews every submission. Anything it flags or is unsure about (risky or needs_human) goes to a stronger model for a second opinion.
  - **Why it was cut:** It's only worth building once a harder eval set shows the cheaper model missing things. Today Claude Haiku 5.5 scores 17/17 risky and 16/16 safe in all 3 runs, so a second model would add cost and time without catching anything more. See EVALS.md.
  - **Steps to build it:**
    1. Add a second model to config.json.
    2. Route flagged or needs_human results to it.
    3. Record both verdicts.
    4. Compare cost and accuracy in EVALS.md.
- **Parallel approvals**
  - **What it is:** The Super admin chooses, per tool, whether the specialist reviews happen in order (today) or at the same time. In parallel mode, every chosen area reviews at once. The tool moves to publish only when all of them have approved, and any rejection ends the review.
  - **Why it was cut:** Reviews in a fixed order (DECISIONS.md #11) were enough for now and keep "whose turn is it?" simple.
  - **Steps to build it:**
    1. Add an "in order / at the same time" choice to the routing step, saved with the tool's own steps.
    2. In parallel mode, treat every review step as open at once: any specialist from a chosen area can decide their area's step, in any order.
    3. Move to the publish step only when every review step is approved; end the review at the first rejection.
    4. Keep no self-approval at every step and one person per step (each reviewer must be a different person from whoever decided any other step).
    5. Show every open review in the Review queue for each matching Specialist.
    6. Add tests: reviews decided in any order, publish waits for all, a rejection ends it, self-approval refused at every parallel step, and in-order mode unchanged.
  - **Open questions:**
    - **Progress line:** how does it show steps happening at once? For example, the parallel reviews stacked side by side between "Route" and "Publish", each marked done or waiting.
    - **A rejection while another review is still open:** does the other specialist's open review close at once and show "not reached"? Can they still add a comment? Is the tool's owner told which review rejected it?
- **Browser tests (Playwright)**
  - **What it is:** Automated tests that open the real pages in a browser and click through them as each persona: submit a tool, route it to two areas, approve each review, publish, and check what each persona sees.
  - **Why it was cut:** The approval rules and the "can I act / why not" logic are tested in Python, and Playwright needs a large browser download and setup time. See DECISIONS.md #12.
  - **Steps to build it:**
    1. Install Playwright for Python and its browser into `.venv` (not committed).
    2. Start the app on a throwaway database with the fake AI, so tests never call the real API.
    3. Write a few journeys: the full multi-specialist approval, a refused self-approval message, a rejection that needs a comment, and the Specialist's filtered queue.
    4. Run them with the rest of the tests, and make them easy to skip on a computer without the browser.
- **Move the front end to React**
  - **What it is:** Rebuild the plain HTML and JavaScript screens in React, with reusable components (for example the progress line and the persona dropdown).
  - **Why it was cut:** Three screens don't need a framework, a build step or Node.js. See DECISIONS.md #12.
  - **When to switch:** when there are more than a handful of screens, when shared pieces like the progress line are reused in many places, when there's a lot of live-updating state, or when several people work on the front end.
  - **Steps to build it:**
    1. Set up React with Vite, and have FastAPI serve the built files.
    2. Turn the shared pieces (persona dropdown, progress line, flag and AI advice panels) into components.
    3. Rebuild the screens one at a time, keeping the same API calls.
    4. Add component tests, and browser tests if not already done.
- **Update a published tool**
  - **What it is:** The builder can submit a change to a tool that's already published. The change becomes a new version that goes through the full review again, with no self-approval. The current published version stays in the catalogue until the new one is approved.
  - **Why it was cut:** Today a published tool can't be changed, which keeps versions and history simple for the demo.
  - **Steps to build it:**
    1. Let the owner start a new draft version from a published tool, linked to it.
    2. Run the rule-based checks and the AI pre-review on the new version, then the full approval flow, with no self-approval at every step.
    3. Keep the current version in the catalogue while the new one is in review; swap them only when the new one is published.
    4. Keep every version, and show who changed what and when (for example, the template and rationale before and after).
    5. Give each tool its own **decision log**, like DECISIONS.md but per tool. Every version adds one entry: what changed, why (in the builder's words), who approved or rejected it at each step with their comments, and the date. Entries are never edited or deleted. This is the per-tool part of the "Full audit trail for a real firm" item below.
    6. Show the log by role:
       - **Builders:** the full log for their own tools.
       - **Approvers:** the full log.
       - **Tool users:** only a short "what changed" note per version, without reviewer comments.
    7. When someone personalises a tool from the catalogue, show a short **"Why it's built this way"** note listing the key decisions and conditions from the tool's decision log (for example, "The disclaimer must stay: required by compliance"). Then they know what's safe to change and what a change would affect. Reviewers' internal comments stay hidden from tool users.
    8. Add tests: a tool user personalising a tool sees the "Why it's built this way" note but no reviewer comments; the old version stays visible during review; the swap happens only on approval; a rejected version leaves the old one in place; the owner can't approve their own change; a log entry can't be edited or deleted; tool users never see reviewer comments.
  - **Open questions:**
    - **Small changes:** does fixing a typo or a wording change need the full review, or a lighter one? Who decides what counts as small?
    - **People's own copies:** what happens to copies people already personalised and saved from the old version? Are they told about the update, and can they move to the new version?
- **Practice versions**
  - **What it is:** A practice can adapt a published tool for its own use. How much review the change needs depends on what it touches.
  - **Why it was cut:** Separate practice libraries are out of scope for now (DECISIONS.md #2). Which changes need which review still has to be confirmed with each specialist area.
  - **Steps to build it:**
    1. Let a practice create a practice version of a published tool, linked to the original and to its decision log (see "Update a published tool").
    2. Route the change by what it touches:
       - **Filling in template values or changing wording:** no specialist review.
       - **Changing the data source** (for example, a different market data provider): technology review, plus compliance if the data reaches clients.
       - **Changing anything client-facing or locked** (such as a required disclaimer): the specialist who owns that part.
    3. The practice admin reviews every practice version, with no self-approval at any step.
    4. Record each practice version in its own decision log, linked to the original's.
    5. Add tests: a wording-only change needs only the practice admin; a data-source change goes to technology, and to compliance when the data reaches clients; changing a locked part goes to its owning specialist; the practice admin can't approve their own practice version.
  - **Open questions (not yet confirmed):**
    - **Scope changes:** does changing the scope (for example, a single stock versus a whole sector) need review, and who decides what counts as a scope change?
    - **Small or cosmetic changes:** which ones need a specialist review? For example, does changing an office address need compliance review? Confirm with each specialist area before building.
- **Notifications**
  - **What it is:** When a tool reaches someone's step, notify them by email or a chat tool such as Microsoft Teams, with a link to the tool. Also notify the builder when their tool is approved, rejected (with the reason) or published.
  - **Why it was cut:** It needs a real email or chat service, and this is a demo with no real systems (BRIEF.md "Out of Scope"). The Review queue's "Waiting on me" view covers the need for now.
  - **Steps to build it:**
    1. After each decision, work out who needs to know: whoever must act next (Super admin, or the specialists for the next area), and the builder.
    2. Send a short message with a link to the tool, through a replaceable "notifier" so email and Teams can be swapped.
    3. For a rejection, include the reviewer's reason (DECISIONS.md #12).
    4. Record each notification sent, so it's possible to check who was told and when.
    5. Add tests with a pretend notifier: the right people are told at each step, the builder gets the reason on rejection, and a failing notifier doesn't stop the decision.
  - **Open questions:**
    - **Avoiding notification overload:** one message per event, or a daily digest? Should people choose?
    - **Reminders:** after how long should a tool waiting at someone's step trigger a reminder, and who else is told if it keeps waiting?
    - **If the notification service is down:** decisions and the Review queue must keep working regardless. Should missed notifications be retried later, and how are duplicates avoided?
- **Ticketing integration**
  - **What it is:** When a tool reaches a specialist step, create a ticket in that reviewer's ticketing system (generic, for example Jira or ServiceNow), with a link back to the tool. When the ticket is approved or rejected, update the tool.
  - **Why it was cut:** It needs a real outside system, and this is a demo with no real systems (BRIEF.md "Out of Scope").
  - **Steps to build it:**
    1. When a review step becomes current, create a ticket in the specialist area's system, with a link to the tool and the step it's for.
    2. Store the ticket's id on that step, and show it in the progress line.
    3. When the ticket is approved or rejected, record the decision on the tool through the same approval rules as the review screen.
    4. Add tests with a pretend ticketing system: ticket created at the right step, a decision synced back, a self-approval refused, and the system being down.
  - **Open questions:**
    - **Syncing decisions back:** how does a decision made in the ticket reach the tool? A notification from the ticketing system when the ticket changes (a webhook), regular checking, or a person clicking a link?
    - **No self-approval across both systems:** how do we know the person who approved the ticket is the same person as in the registry, and not the tool's owner? This needs a reliable match between the two systems' user accounts. The registry should still refuse the decision if they don't match.
    - **If the ticketing system is down:** do reviews wait, can specialists decide in the registry directly, and how are missed tickets created later without making duplicates?
- **Full audit trail for a real firm**
  - **What it is:** A complete record of who did what and when, which nothing can delete or quietly change. Each tool's own decision log (see "Update a published tool" above) is the per-tool part of it.
  - **Why it was cut:** It isn't needed for a demo with made-up data. Today the approval history is already add-only, the database keeps every AI review (the review screen shows only the latest), git keeps every version of the sample advice, and `logs/` records each AI call with no set time limit.
  - **Steps to build it:**
    1. Never delete or overwrite AI reviews or approval decisions. Make them add-only in the database, so a change is a new row, not an edit.
    2. Keep old AI reviews and show the full history in the review screen, not just the latest one.
    3. Keep the rule-based check results from every submission too (today a new run replaces the old ones).
    4. Keep AI call logs for a set time (a retention period agreed with compliance), then remove them on schedule.
    5. Record who changed the sample advice and when, alongside the file itself.
    6. Keep sample and demo data out of the live database entirely, in a separate demo or test environment, so sample reviews never mix with real records or reports. Today they share one database, kept apart by the `is_sample` label, which is fine for a demo.
    7. Add tests: an update or delete of a review or decision is refused; history shows every review; old logs are removed only after the retention period.
- **Real sign-in instead of the persona dropdown**
  - **What it is:** In a real firm, people sign in, and their role, practice and specialist area come from the firm's directory. Nobody can pick a persona.
  - **Why it was cut:** This is a demo with made-up people, so a persona dropdown is enough (DECISIONS.md #3; BRIEF.md "Out of Scope").
  - **Steps to build it:**
    1. Sign people in through the firm's sign-in service, instead of the `X-Persona` header.
    2. Read each person's role, practice and specialist area from the firm's directory, not from the made-up personas.
    3. Remove the persona dropdown and the demo banner.
    4. Reword messages that tell people to pick a different persona. For example, the Review queue refusal becomes "The Review queue is only for Practice admins, Super admins and Specialist reviewers. Ask an admin if you need access.", and "Pick a persona first" becomes a sign-in prompt.
    5. Add tests: nobody can act as someone else; roles come from the directory; a person removed from the directory loses access.
- **Spot overlap**
  - **What it is:** Practices can see a short summary of the tools other practices are building (name, purpose, practice, status and contact person), so they can spot duplicates and team up.
  - **Why it was cut:** Not needed for the demo, and it has to be designed with least privilege in mind (DECISIONS.md #13). The unique-name check already flags exact duplicates.
  - **Steps to build it:**
    1. Add an "In progress across the firm" list showing only the summary fields.
    2. Keep review details (rule flags, AI advice and reviewer comments) private to the tool's own practice and its reviewers.
    3. Add a "contact the builder" link, so people can team up rather than build the same tool twice.
    4. Add tests: other practices see only the summary fields; rule flags, AI advice and reviewer comments are never included for them.
  - **Links to:** least privilege (DECISIONS.md #13). The summary list is a deliberate, limited exception to "see only what your job needs".
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo

## In Progress

## Done
