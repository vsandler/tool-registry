# Backlog

## To Do
- **Confirm AI advice**
  - **What it is:** instead of typing a comment, a specialist can confirm the AI advice by selecting which of the AI's points they agree with. The selected points become the recorded reason. The history shows it as the person's decision, for example "Devon Marsh confirmed these AI points", never as the AI deciding.
  - **Why it matters:** it saves typing when the AI's points are right, while the person still makes and owns the decision. The risk is rubber-stamping (automation bias: agreeing with the AI without really checking), so each reviewer's agreement rate and decision time are tracked.
  - **Steps to build it:**
    1. In the decision panel, show each of the AI's points with a checkbox, next to the Comment box. Selecting points is an alternative to typing a comment, not an extra step.
    2. Send the selected points with the decision. The back end checks they are exactly points from that tool's saved AI advice, and saves them as the decision's reason, with who decided and when.
    3. Count confirmed points as the reason a rejection needs, so a rejection can rest on selected points instead of a typed comment. The no self-approval and order rules stay the same.
    4. In the history, label it as the person's decision: "Devon Marsh confirmed these AI points", followed by the points. Never "the AI approved" or "the AI rejected".
    5. For each reviewer, record how often they confirm the AI's points and how long they take from opening a tool to deciding. Show it to the Super admin, with a note when someone agrees almost every time or decides very fast.
    6. Add tests: only points from the saved advice are accepted; the history names the person, not the AI; a rejection with selected points is accepted; a made-up point is refused; the agreement rate and decision time are recorded.
  - **Open questions:**
    - **Thresholds:** what agreement rate or decision time counts as "too high" or "too fast", and who reviews it?
    - **Partial agreement:** can a reviewer confirm some points and add a typed comment for the rest?
    - **Privacy:** who may see each reviewer's numbers, and is it framed as coaching rather than a score?
- **Require a reason to approve against the AI's advice**
  - **What it is:** when the AI's advice flagged a tool, an approver who approves it anyway must say why, the same way a rejection needs a reason today. The reason is saved with the decision and shown in the history, so it's clear a person chose to go against the advice.
  - **Why it matters:** the AI's advice is only advice (it never decides), but going against it should be a deliberate, recorded choice, not a click. It pairs with "Confirm AI advice" above: agreeing and disagreeing with the AI both leave a reason.
  - **Steps to build it:**
    1. The back end works out "approving against the advice" from the tool's saved AI review, so the screen never decides it.
    2. Refuse such an approval without a reason, in plain words next to the Comment box (for example "The AI flagged this tool. Say why you're approving it anyway."), using the same minimum length as a rejection comment.
    3. Send it in `my_action` (for example `needs_reason: true`), so the Comment box's hint says a reason is needed before the person clicks Approve.
    4. Label it in the history, for example "Approved against the AI's advice: …".
    5. Add tests: a flagged tool approved with no reason is refused and nothing is saved; with a reason it's accepted and labeled; a tool the AI called safe needs no reason; the hint matches what the back end refuses.
  - **Open questions:**
    - **"Needs a human":** when the AI couldn't give advice (for example it timed out), does approving need a reason too?
    - **Which steps:** every approval step, or only the specialist reviews and the final publish?
    - **Rule flags:** should approving a tool with rule flags (not just AI flags) also need a reason?
- **"New" badge on the Catalog tab**
  - **What it is:** the Catalog link in the navigation shows a "new" badge (for example "Catalog · 2 new") when tools were published since the person last looked at the Catalog. Opening the Catalog clears it, and the new tools are marked on their cards.
  - **Why it matters:** people find out about new tools without being told separately.
  - **Steps to build it:**
    1. The back end records when each person last opened the Catalog, and counts the published tools they may see that were published after that. Tools don't record when they were published yet, so add a `published_at` date, set at the publish step.
    2. Send the count with the persona (for example `new_in_catalog`), the same way `can_submit` is sent, so the navigation only displays it.
    3. Opening the Catalog marks it as seen, and the cards of tools published since the last visit show "New".
    4. Write it out for screen readers ("Catalog, 2 new tools"), not just a colored dot.
    5. Add tests: a tool published after the last visit counts; one the person may not see (another practice's practice-only tool) never counts; opening the Catalog clears the count; a first visit doesn't mark everything new.
  - **Open questions:**
    - **First visit:** is everything new, or nothing?
    - **Where "last looked" is kept:** in the back end (works on any device), or only in this browser (simpler, but lost on another device)? With real sign-in, the back end is the natural home.
- **Revisit length limits with real data**
  - **What it is:** the length limits (DECISIONS.md #22: name 100, description 500, template 5,000, rationale 1,000 and comments 1,000 characters) were set from made-up text. Each is at least twice the longest text in the seed data and eval cases (the name about 2.4 times, the template about 13 times). Real tools may be longer.
  - **Why it matters:** a limit that's too low refuses good tools; one that's too high lets the cost of an AI review grow.
  - **Steps to build it:**
    1. In production, log the length of each box of every real submission (the lengths only, never the text, which may hold client details).
    2. Log each refusal for length: which box, how far over, and whether the person then shortened it and submitted.
    3. Review the numbers regularly, for example monthly: if good tools keep hitting a limit, raise it; if nothing comes close, consider lowering it.
    4. Keep the rule that each limit is at least twice the longest real submission on record, and update the test that guards it to use the logged lengths.
    5. Record each change and its reason in DECISIONS.md, with the new worst-case cost per review.
  - **Open questions:**
    - **How long to keep the length logs,** and who may see them?
    - **Per-box or per-submission:** should there also be a limit on the whole submission's size, since that's what sets the AI's cost?
- **Live character counter on the Submit form and the Review queue's Comment box**
  - **What it is:** under each text box on the Submit form (name, description, template, rationale) and under the Review queue's Comment box, a counter shows how much of the limit is used as the person types, for example "382 / 5,000 characters". It changes color and says so in words when close to or over the limit.
  - **Why it matters:** today people only find out about a length limit after submitting or deciding, when the back end refuses (DECISIONS.md #22). A counter tells them first.
  - **Steps to build it:**
    1. The back end sends each limit with what the screen already asks for, so the limits stay in one place: `TEXT_LIMITS` with the Submit form (`GET /submit-form`, for example `max_length` on each field in `FORM_FIELDS`), and `MAX_COMMENT` with each tool's `my_action` (for example `comment_max`, next to the `reject_comment_min` it already sends).
    2. Show the counter under each box, updated as the person types, and link it to the box for screen readers (`aria-describedby`). The Comment box's existing hint stays linked too.
    3. Announce it to screen readers only when close to the limit (for example the last 10%) or over it, not on every key press.
    4. Don't stop typing at the limit (no `maxlength`): the back end still checks, and its message still appears next to the box. The counter only displays. The Review queue's test that the decision controls do no checking of their own still applies.
    5. Count characters the same way the back end does (Python's `len`), so the counter and the refusal agree, including for emoji and other unusual characters. The Comment box is counted after trimming spaces at each end, as the back end does.
    6. One shared counter in `web/app.js`, used by both screens, like the progress bar.
    7. Add tests: every limit the Submit form shows matches `TEXT_LIMITS`, and `comment_max` matches `MAX_COMMENT`; both pages read the limits from the back end and have no numbers of their own; no `maxlength` on either page.
- **Clearer Comment hint in the Review queue**
  - **What it is:** the hint under the Review queue's Comment box reads "Optional when approving. To reject, explain why in at least 10 characters. The builder will see it." Someone skimming sees "Optional" first and can miss the rule for rejecting. Put the requirement first: "Required to reject (at least 10 characters). Optional when approving. The builder will see it."
  - **Why it matters:** a rejection without a proper comment is refused (DECISIONS.md #12), so the rule people are most likely to trip over should be the first thing they read.
  - **Steps to build it:**
    1. Reword the hint in `web/queue.html` (the Comment box's `hint`), keeping the number from the back end's `reject_comment_min`, not typed into the page.
    2. Keep the hint linked to the Comment box for screen readers (`aria-describedby`).
    3. Add a test: the hint starts with the requirement to reject, and still reads its minimum from `reject_comment_min`.
    4. If "Require a reason to approve against the AI's advice" is built later, update this hint to match, for example "Required to reject, and to approve a tool the AI flagged (at least 10 characters). The builder will see it.", worded from the back end's `needs_reason` so the hint and the refusal can't disagree.
- **Configurable approval order**
  - **What's fixed today:** the Super admin already picks which specialist areas review each tool, and in what order (DECISIONS.md #11). What's fixed is the frame around that:
    - the Super admin always routes first and publishes last;
    - the only steps in between are specialist reviews (for example, there's no Practice admin sign-off step);
    - the three specialist areas (technology, compliance, marketing) are set in the code;
    - no area is ever required: the Super admin could route a firm-wide tool past compliance.
  - **What would become configurable:** admins set the default order, including kinds of step other than specialist reviews, keep the list of specialist areas, and set rules for which areas a tool must go through.
  - **Why it was cut:** a configurable order needs more back-end work than the weekend build allowed (DECISIONS.md #1). Each tool's steps are already saved as an ordered list, so it needs no rewrite.
  - **Steps to build it:**
    1. Add a settings screen where a Super admin can add, remove and reorder the steps in the default order, including steps other than specialist reviews (for example a Practice admin sign-off).
    2. Let admins keep the list of specialist areas, instead of it being set in the code.
    3. Add rules for required areas, for example based on visibility (every firm-wide tool goes through compliance). At routing, the Super admin starts from the required areas, can add more and change the order, but can't remove a required one.
    4. Save each order as an ordered list of steps (the same list format used today).
    5. Keep today's order (route, the chosen specialist reviews, publish, with nothing required) as the default when nothing has been set up.
    6. Add tests: a custom order runs in the right sequence; a required area can't be removed at routing; new kinds of step keep no self-approval and one person per step; the default still works.
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
    6. Change the progress line's "Skipped: rejected at step N" to "On hold: waiting for the builder to fix and resubmit" while the builder can still resubmit. It's one sentence in the back end (`skipped_reason` in `get_progress`), so the screens need no change.
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
  - **What it is:** The builder can submit a change to a tool that's already published. The change becomes a new version that goes through the full review again, with no self-approval. The current published version stays in the catalog until the new one is approved.
  - **Why it was cut:** Today a published tool can't be changed, which keeps versions and history simple for the demo.
  - **Steps to build it:**
    1. Let the owner start a new draft version from a published tool, linked to it.
    2. Run the rule-based checks and the AI pre-review on the new version, then the full approval flow, with no self-approval at every step.
    3. Keep the current version in the catalog while the new one is in review; swap them only when the new one is published.
    4. Keep every version, and show who changed what and when (for example, the template and rationale before and after).
    5. Give each tool its own **decision log**, like DECISIONS.md but per tool. Every version adds one entry: what changed, why (in the builder's words), who approved or rejected it at each step with their comments, and the date. Entries are never edited or deleted. This is the per-tool part of the "Full audit trail for a real firm" item below.
    6. Show the log by role:
       - **Builders:** the full log for their own tools.
       - **Approvers:** the full log.
       - **Tool users:** only a short "what changed" note per version, without reviewer comments.
    7. When someone personalizes a tool from the catalog, show a short **"Why it's built this way"** note listing the key decisions and conditions from the tool's decision log (for example, "The disclaimer must stay: required by compliance"). Then they know what's safe to change and what a change would affect. Reviewers' internal comments stay hidden from tool users.
    8. Add tests: a tool user personalizing a tool sees the "Why it's built this way" note but no reviewer comments; the old version stays visible during review; the swap happens only on approval; a rejected version leaves the old one in place; the owner can't approve their own change; a log entry can't be edited or deleted; tool users never see reviewer comments.
  - **Open questions:**
    - **Small changes:** does fixing a typo or a wording change need the full review, or a lighter one? Who decides what counts as small?
    - **People's own copies:** what happens to copies people already personalized and saved from the old version? Are they told about the update, and can they move to the new version?
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
- **Fill blanks from an approved data source**
  - **What it is:** A tool's blanks can be filled automatically from a firm-approved data source that already filters by permission. The registry asks the source as the person using the tool, with their own access. It never uses a shared account that sees everything, so the source's permission rules always apply.
  - **More than one source per tool:** a tool can be approved with more than one data source (for example, two market data providers). The person using it picks which approved source to fill from, with no new review. Adding a source the tool wasn't approved for goes back through technology review (and compliance if the data reaches clients), as in "Practice versions". The downloaded copy notes which source was used.
  - **Why it was cut:** This is a demo with no real systems or data sources (BRIEF.md "Out of Scope"). For now people type the values into the Catalog's Personalize form themselves.
  - **Steps to build it:**
    1. Keep a list of approved data sources. Only sources on that list can be used.
    2. Let a tool link its blanks to one or more approved sources. Adding a source to a tool needs technology review, plus compliance if the data reaches clients (see "Practice versions").
    3. When someone personalizes the tool, let them pick one of the sources the tool was approved for, with no new review. Ask the source as that person, using their own access, never a shared account. Whatever the source won't show them stays empty.
    4. Use the filled values only for that person's copy. Never save them in the registry and never send them to the AI reviewer.
    5. Note in the downloaded copy which source was used.
    6. Add tests with pretend data sources: each person gets only what their own access allows; a source not on the approved list is refused; a source the tool wasn't approved for is refused at personalizing; picking between a tool's approved sources needs no review; adding a source to a tool goes to technology review, and to compliance when the data reaches clients; the download names the source used; filled values never appear in the database or in what the AI reviewer is sent.
  - **Open questions (not yet confirmed):**
    - **Source down or empty:** what happens if the source can't be reached or returns nothing? For example, leave the box for the person to fill in, or stop the download.
    - **Editing filled values:** can people change a filled value before downloading, or must it stay as the source gave it?
    - **Field names differ by source:** each source may name its fields differently (for example "ticker" versus "symbol"), so each approved source needs its own mapping to the tool's blanks. Who sets and reviews that mapping?
    - **Mixing sources:** can one copy mix sources (some blanks from one source, some from another), or is it one source per copy?
- **Admin-managed practice list**
  - **What it is:** The practices a tool can belong to come from a list that admins keep. On the Submit form, a "My practice isn't listed" link sends a request asking an admin to add it. Builders never type their own practice name, so there are no near-duplicates such as "Tax" and "Tax team".
  - **Why it was cut:** For the demo, the Submit form's Practice dropdown lists the practices people already belong to (`GET /submit-form`), which is enough with made-up data.
  - **Steps to build it:**
    1. Store the practice list, and let an admin add, rename or retire a practice.
    2. Fill the Submit form's Practice dropdown from that list.
    3. Add "My practice isn't listed": the builder gives the practice's name and a short reason, and the request goes to an admin's list of requests.
    4. On submit, the back end refuses a practice that isn't on the list, with a plain message next to the Practice box.
    5. Add tests: only practices on the list are accepted; only admins can change the list; a request reaches an admin; a retired practice can't be picked for new tools.
  - **Open questions (not yet confirmed):**
    - **Who approves a request:** the Super admin, or any admin? Can a Practice admin add only their own practice?
    - **While waiting:** what does the builder do: keep the tool as a draft, or submit it as firm-wide?
    - **Renames and merges:** what happens to existing tools when a practice is renamed, merged or retired?
    - **Telling people:** should the request and its answer use the "Notifications" item?
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
- **Approved outside the registry**
  - **What it is:** sometimes a step is signed off somewhere else, for example a compliance approval given in a ticket or a meeting. Only the Super admin can mark that step "approved elsewhere", recording who approved it, when, and a reference (such as a ticket number). It's shown, clearly labeled, in the history and the progress line, for example "Approved outside the registry by Sam Thistle on 17 Nov 2026 (ref. COMP-1042), recorded by Riley Ashgrove".
  - **Link to "Ticketing integration" above:** once that exists, the reference becomes a link to the ticket, and a ticket approved in the other system could fill this in instead of the Super admin typing it.
  - **Why it was cut:** the demo has no outside systems, and every decision is made in the registry.
  - **Steps to build it:**
    1. A Super admin-only action on the current step, "Mark approved elsewhere", asking for who approved it, when and a reference, all required and checked by the back end.
    2. Record it as an approval of that step, marked as outside the registry, with who recorded it. It's add-only, like every decision.
    3. Keep the usual rules: steps in order, the tool's owner can't be the approver or the one recording it, and a specialist step still needs someone who decided no other step.
    4. Label it in the history and the progress line ("Approved outside the registry"), with the reference.
    5. Add tests: only the Super admin can do it; each detail is required; it's labeled in the history; the owner can't be named as the approver; it can't skip a step.
  - **Open questions:**
    - **Evidence:** is a reference enough, or should the Super admin attach the sign-off itself (an email or document)?
    - **People outside the registry:** can the approver be someone with no account, and how are they named?
    - **Mistakes:** if it was recorded by mistake, is it undone by a new history entry, so nothing is deleted?
- **Let anyone propose a tool**
  - **What it is:** today Builders, admins and specialists can submit tools, and Tool users are refused (DECISIONS.md #19). Later, anyone could propose a tool. Whoever submits it becomes its builder (the owner), with the same rules as any builder: they can't approve or reject it, they see the rule flags and tips, and they're told why if it's rejected.
  - **A Tool user becomes a Builder** when they make their first submission: their role changes, so from then on they're treated as a Builder everywhere (the persona label, the "Submit a tool" link, and their own tools).
  - **Why it was cut:** for the demo, Tool users only use published tools, which keeps the personas' roles clear.
  - **Steps to build it:**
    1. Allow every role in `SUBMIT_ROLES` (`registry/personas.py`), so "Submit a tool" shows for everyone through `can_submit`.
    2. Show "Built by" as whoever submitted, and use their practice as the tool's practice, as today.
    3. On a Tool user's first submission, change their role to Builder, in the same save as the submission, and record the change (who, when, which tool) so it's traceable.
    4. Add tests: a Tool user submits, becomes the owner and a Builder, can't approve it, and sees their tool's progress; a refused submission (for example a missing rationale) doesn't change their role.
  - **Open questions:**
    - **Extra step for proposals:** should a tool proposed by someone who isn't a Builder first be adopted by a Builder before review?
    - **Support:** who helps first-time submitters improve a flagged tool?
    - **Role source:** with real sign-in, roles come from the firm's directory. Does the registry change the role itself, or ask the directory to?
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
    4. Show the summary to Practice admins and the Super admin too. In their Review queue, add a **"Looks similar"** flag when a tool looks like one another practice is building, so they can connect the two builders. The flag shows only the summary fields of the other tool, never its review details.
    5. Add tests: other practices see only the summary fields; rule flags, AI advice and reviewer comments are never included for them; a similar tool from another practice raises the flag in the admin's queue without showing its review details.
  - **Links to:** least privilege (DECISIONS.md #13). The summary list is a deliberate, limited exception to "see only what your job needs".
- **Support skills, hosted HTML tools and shared Claude artifacts**
  - **What it is:** today every tool is a prompt template: text with `{{blanks}}`. Real tools would be Claude skills (instructions, and often code, that the AI follows) and interactive HTML tools built in Claude, delivered one of two ways: hosted on a firm-owned subdomain, or shared as a Claude artifact. Both kinds can run code, call APIs or reach data, so they need stronger checks than a template, and they take inputs while running instead of blanks filled in up front.
  - **Why it was cut:** a prompt template is the simplest unit that proves the governance workflow (submit, check, AI pre-review, approve, publish, reuse). The same pipeline carries over; the checks get stronger.
  - **Steps to build it:**
    1. **Tool type field:** add a type to each tool (prompt template, skill or HTML tool), chosen on the Submit form and shown in the Review queue and the Catalog. Existing tools are prompt templates.
    2. **Access list:** a skill or HTML tool declares what it can reach (for example which APIs, data sources, files or network addresses). Reviewers see the list, approval covers exactly that list, and anything not on it is refused when the tool runs.
    3. **Sandbox test before approval:** run the tool in a sealed-off test environment with made-up data, and record what it actually tried to reach. Anything it tried that isn't on its access list is flagged to the reviewers. The tool can't be approved until the test has run.
    4. **AI pre-review of instructions and code:** extend the agent's rules to read a skill's instructions and any code, not just template text: hidden data sends, credentials, reaching beyond the access list, and anything that skips human checks. Still advice only.
    5. **Version re-review:** every new version goes through the full review again, including the sandbox test, with no self-approval (see "Update a published tool"). The published version stays in use until the new one is approved.
    6. **Prompt-injection checks on skill instructions:** check that a skill's instructions treat the content it reads (documents, web pages, user input) as data, not as orders, and add eval cases where that content tries to take over the skill.
    7. **Delivery field:** an HTML tool records how it reaches people: **firm subdomain** or **Claude artifact**. It's chosen on the Submit form and shown to reviewers, approval covers that choice, and changing it is a new version that needs a full review.
    8. **Delivered on the firm subdomain:**
       - **Publish means deploy, unpublish means take it offline:** publishing deploys the tool to the firm-owned subdomain; unpublishing takes it offline.
       - **Company sign-in (SSO):** people reach a tool only through the firm's sign-in, with access matching the tool's visibility (firm-wide, or practice-only for that practice).
       - **Isolation:** each tool runs separately from the others (for example, each at its own address under the subdomain), so one tool can't read another's browser data.
    9. **Delivered as a shared Claude artifact:**
       - **Sharing scope matches visibility:** a firm-wide tool is shared with the firm; a practice-only tool is shared only with that practice, never org-wide.
       - **No public links, ever:** a tool shared by a public link is refused, at review and if it's ever found published that way.
       - **Publish means share, unpublish means unshare:** publishing shares the artifact at the approved scope; unpublishing removes the sharing.
    10. Add tests and eval cases for each step: a tool reaching beyond its access list is refused; a skill or HTML tool can't be approved before its sandbox test; a new version, or a change of delivery, needs a full review; the AI flags credentials and hidden data sends in code; the injection cases are caught; publishing deploys and unpublishing takes the tool offline; someone outside a practice-only tool's practice is refused at sign-in; one tool can't read another's browser data; an artifact shared wider than its visibility (for example a practice-only tool shared org-wide) is refused; a public link is refused; unpublishing an artifact removes its sharing.
  - **Open questions:**
    - **Who tests:** who runs and reads the sandbox test: the technology specialists, or an automatic step before routing?
    - **Changing access:** does widening a published tool's access list need the full review, or only a technology review?
    - **Personalizing:** what replaces "fill in the blanks" for a skill or HTML tool, for example settings chosen at install time?
    - **Checking artifact sharing:** can the registry read and change an artifact's sharing settings itself, or does a reviewer check them by hand? If by hand, how is a later change to the sharing noticed?
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo

## In Progress

## Done
- **Design polish: the progress bar and the Review queue's empty views** (2026-11-18)
  - The progress line is now one connected bar on the Submit page and in the Review queue: a circle per step (✓ done, ● now, ✕ rejected, – skipped, empty for later), joined by a line that turns green up to the last done step. Side by side when there's room, stacked on a phone. Screen readers still hear each step's state in words.
  - Review queue: when the list is empty, the "Pick a tool" box is left out and the empty message uses the full width; when a just-decided tool is still shown, the two boxes' tops line up.
- **Design: stacked progress bar in the Review queue's narrow details box** (2026-11-18)
  - In the details box, a tool with more than 3 steps shows them stacked, so the text isn't squeezed. 3 or fewer stay side by side, and the Submit page is unchanged. DECISIONS.md #21.
- **Publish confirmation says where the tool went** (2026-11-18)
  - "Decision recorded. Published firm-wide." or "… Published to the Tax practice only.", worded by the back end (`published_label`). DECISIONS.md #21.
- **Published badge and bold publish line in the Review queue** (2026-11-18)
  - After publishing, a green "Published · Firm-wide" (or "Published · Tax practice only") badge sits next to the tool's name, worded by the back end (`published_badge`). The history's "Published as …" is in bold, picked out by the back end's `detail_kind`.
