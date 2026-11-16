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
- **Hub-and-spoke routing**
  - **What it is:** After each specialist approves, the tool returns to the Super admin. The Super admin can then send it to another specialist, as many times as needed, or publish it as practice-only or firm-wide.
  - **Why it was cut:** The fixed three-step order (route, one specialist, publish) was enough for the weekend build and keeps the approval rules simple. See DECISIONS.md #1.
  - **Steps to build it:**
    1. Let the Super admin's "return" step offer two choices: route to another specialist area, or publish.
    2. Store each routing as its own entry in the approval history, so a tool can have several specialist reviews.
    3. Stop the same specialist area from being routed twice in a row by mistake, or ask the Super admin to confirm it.
    4. Show the review queue with every specialist review so far, not just the latest.
    5. Keep "specialist must be a different person" and "no self-approval" for every round.
    6. Add tests: two specialist rounds then publish; publish straight after one round; a rejection in any round ends the review.
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
