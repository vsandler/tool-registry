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
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo

## In Progress

## Done
