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
  - **What it is:** A complete record of who did what and when, which nothing can delete or quietly change.
  - **Why it was cut:** It isn't needed for a demo with made-up data. Today the approval history is already add-only, the database keeps every AI review (the review screen shows only the latest), git keeps every version of the sample advice, and `logs/` records each AI call with no set time limit.
  - **Steps to build it:**
    1. Never delete or overwrite AI reviews or approval decisions. Make them add-only in the database, so a change is a new row, not an edit.
    2. Keep old AI reviews and show the full history in the review screen, not just the latest one.
    3. Keep the rule-based check results from every submission too (today a new run replaces the old ones).
    4. Keep AI call logs for a set time (a retention period agreed with compliance), then remove them on schedule.
    5. Record who changed the sample advice and when, alongside the file itself.
    6. Keep sample and demo data out of the live database entirely, in a separate demo or test environment, so sample reviews never mix with real records or reports. Today they share one database, kept apart by the `is_sample` label, which is fine for a demo.
    7. Add tests: an update or delete of a review or decision is refused; history shows every review; old logs are removed only after the retention period.
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo

## In Progress

## Done
