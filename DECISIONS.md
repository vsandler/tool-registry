# Decisions

_Key choices made for this project, why we made them, and what we gave up._

---

## 1. Fixed approval order

**Decision:** Every tool follows the same three-step approval order:
1. **Super admin routes it.** They approve it for review and send it to one specialist area: AI enablement (technology), compliance, or marketing.
2. **That specialist approves it.** Only a Specialist reviewer from the chosen area can decide this step.
3. **It returns to the Super admin, who publishes it.** They set the visibility (practice-only or firm-wide) and publish.

The same Super admin may do steps 1 and 3. The specialist must be a different person. Nobody approves a tool they own, admins included. A rejection at any step is final for now. Admins can't change the order for now.

**Why:** A configurable order needs more back-end work than we can finish by Saturday evening. The approval steps are saved as an ordered list, not hard-coded, so the configurable version can be added later without a rewrite.

**Trade-off:** Every tool goes through the same path, and only one specialist area reviews it, even when a tool would benefit from more than one. The configurable order and hub-and-spoke routing (several specialists in turn) are in the BACKLOG.md To Do list.

---

## 2. One catalogue with a visibility label

**Decision:** All tools live in one catalogue. Each tool has a label: **practice-only** or **firm-wide**.

**Why:** Keeps the weekend scope small. One label does most of what separate libraries would do.

**Trade-off:** Practices can't arrange or manage their own library. Separate practice libraries stay in the backlog.

---

## 3. Persona dropdown instead of real sign-in

**Decision:** Users pick who they are from a dropdown (for example, Builder or Super admin) instead of logging in.

**Why:** This is a demo with made-up users, so there's nothing to protect and no real accounts to check.

**Trade-off:** There's no real security. Anyone can act as any role, so this isn't safe to use with real people or data.

---

## 4. The AI agent uses Claude Haiku 5.5 (confirmed after comparing with Sonnet 5.5)

**Decision:** The AI pre-review agent uses Claude Haiku 5.5. It started on Haiku, and the 8d comparison on 2026-11-16 confirmed that choice. `config.json` stays `claude-haiku-5-5`.

**How we compared:** both models ran the same eval: 34 made-up cases (18 risky, 16 safe), each 3 times, with the same instructions and effort level. Full table in EVALS.md ("8d").

| | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Score | 18/18 risky, 16/16 safe in every run | 18/18 risky, 16/16 safe in every run |
| Missed or inconsistent cases | none | none |
| Cost per review (average) | $0.00018 | $0.0035 (about 19.5× Haiku) |
| Cost per 10,000 reviews (estimate) | about $2 | about $35 |
| Response time (average / slowest) | 1.73 s / 3.52 s | 2.62 s / 6.77 s |

**Why Haiku:** the rule set before the comparison was "if both score 100%, cost and speed decide". Both scored 100%, so Sonnet's extra cost bought nothing we could measure. Haiku is about 20 times cheaper and about 1.5 times faster, and its slowest review leaves more room under the 10-second target.

**Trade-off:** a smaller model might still miss risks a larger one would catch. Our test set may simply be too easy to show the difference, since both models got every case right.

**The path if that changes:** if a harder eval set (BACKLOG.md "Make the eval set harder") shows Haiku missing risks that Sonnet catches, build the model cascade (BACKLOG.md "Model cascade"). Haiku would keep reviewing every submission, and anything it flags or is unsure about would go to Sonnet for a second opinion. Most reviews would stay at Haiku's cost, with Sonnet's judgement where it matters. Then compare cost and accuracy in EVALS.md before switching it on.

---

## 5. Codex on the free ChatGPT plan for the outside review

**Decision:** The outside code review uses Codex on the free ChatGPT plan, running on this computer.

**Why:** Hands-on Codex experience is a requirement for the role, and a second AI tool gives an independent review.

**Trade-off:** The free plan has a usage cap. If we hit it, we upgrade to ChatGPT Plus.

---

## 6. The AI pre-review runs on every submit, as advice only

**Decision:** Every submission runs the six rule-based checks, then the AI pre-review. The AI's verdict (risky, safe or needs human), its issues and its reason are saved and shown to reviewers in the admin review queue, marked `advice_only`. The AI never approves, rejects or moves a tool along. If the AI fails, the tool is still submitted and marked "needs human".

**Why:** Running it every time means reviewers always have the AI's notes without having to ask for them. Keeping it advice-only follows the brief: anything flagged goes to a human, and nothing is auto-rejected. It also limits the damage of an AI mistake, because a wrong "safe" still meets three human approval steps.

**Trade-off:** Each submit costs a little money (about $0.0002) and takes 1–3 seconds longer. Reviewers might lean on the AI's "safe" too much. The rule-based flag and the AI flag are kept separate, so it's always clear which came from a fixed rule and which from the AI's judgement.

---

## 7. The rationale check is split between the rules and the AI

**Decision:** The rule-based `has_rationale` check catches missing, empty or very short rationales (under 20 characters). The AI only judges whether a rationale that is present actually makes sense, for example circular, placeholder or unrelated text. The empty and "n/a" cases moved from the AI eval set to the rule-based tests, and a test keeps empty rationales out of the AI eval set.

**Why:** "Is there a rationale?" is a yes/no question that a free, instant rule answers perfectly. "Does it make sense?" needs judgement, which is what the AI is for. Splitting them means each is tested on the job it actually does.

**Trade-off:** The AI may still mention an empty rationale in passing, so reviewers can see it twice. A rationale that is long enough but only slightly weak may pass both checks; the human reviewers remain the final check.

---

## 8. Evals run each case 3 times, and one miss counts as a miss

**Decision:** The eval runs every case 3 times. A risky case counts as caught only if it's flagged in all 3 runs. A safe case passes only if it's clean in all 3 runs. Any case whose answer changes between runs is listed as inconsistent. The brief's safe target (at least 80%) must be met in every run.

**Why:** The AI can give different answers to the same submission. A risky tool that slips through once in three would slip through in real use too, so averaging it away would hide a real risk.

**Trade-off:** Each full eval costs three times as much (about $0.02 instead of $0.007) and takes three times as long. Three runs can still miss a rare wobble.

---

## 9. Fixed sample advice for the seeded tools, not live AI calls

**Decision:** The three seeded sample submissions show fixed, pre-written AI advice copied from a real AI review, stored in `registry/sample_advice.json` and clearly labelled as sample advice. Starting the app makes no AI calls. Real submissions, including the two demo drafts when submitted, always call the AI.

**Options considered:**
- **Fixed sample advice:** free, needs no API key, and gives the same result every time, so demos and tests are predictable. But it can go out of date.
- **Live AI calls when the sample data loads:** always real and current, but costs money every time the app starts fresh, needs a key, and can give slightly different advice each time.

**Why fixed:** Demos should work the same every time, including on a computer without a key, and starting the app shouldn't spend money. The two demo drafts still show the real AI working live.

**How it stays current:** The file records the model and a fingerprint (hash) of the agent's instructions it was made with, plus a fingerprint of each seeded tool's content. A test fails if the model or instructions no longer match `config.json` and the current code, or if a seeded tool is changed, added or removed. Its message explains step by step what changed and which command to run. The advice is refreshed only by hand, with `.venv/Scripts/python -m registry.refresh_sample_advice`. That command never runs automatically, and it keeps the old file if any AI call fails.

**Trade-off:** Someone has to run the refresh command and commit the result after changing the model or instructions. The test makes sure they can't forget, but it does add a manual step.

---

## 10. Front end: three screens and a persona dropdown (approved 2026-11-16)

**Persona dropdown (top bar, every screen).** Shows name, role and practice or specialist area ("Sam Specialist: Specialist reviewer, compliance"), under a banner: "Demo: pick a persona, no real sign-in". *Why:* an approver should always know whose eyes they're looking through, because that decides what they can see and do.

**Review queue (the approver's main screen).**
- **Who sees it:** Super and Practice admins see every tool in review. Specialist reviewers see only tools waiting for their area (option A). The queue is read-only; decisions go through the buttons below. *Why:* Specialists need to find their work, and a short, relevant list helps.
- **The list:** one row per tool: name, current step, who must act next. It opens on **"Waiting on me"**, oldest first, with a switch to "All in review". *Why:* an approver's first question is "what do I need to do?", and oldest first is fair to builders.
- **Two kinds of warning, kept apart:** **"Rule flags"** (facts from the fixed checks) and **"AI advice: you decide"** (the AI's issues and reason, labelled "Sample advice" where it applies). *Why:* an approver can tell a fixed rule from an AI opinion, and never mistakes advice for a decision.
- **Progress line** at the top of the detail panel, built from **this tool's own list of approval steps**, so a tool sent to two specialists shows four steps, e.g. "1 Route → 2 Compliance review → 3 Marketing review → 4 Publish". Each step shows **done** (who, when) or **waiting** (who must act). After a rejection it shows where the tool stopped, with later steps marked "not reached". On the last step, a clear note reads: **"This is the final approval. Approving publishes the tool."** *Why:* an approver sees what's been checked, by whom, what's still to come, and whether their click puts the tool in front of users.
- **Detail panel:** template, rationale, every check, the AI's notes and the full history with comments.
- **Decision buttons appear only when it's your turn.** Step 1: the Super admin picks **one or more specialist areas, in order**. Each becomes its own review step. Review steps: approve or reject. Last step: set visibility (practice-only or firm-wide, with the practice) and publish. When you can't act, a plain sentence says why ("You built this tool, so you can't approve it"; "Waiting for marketing"). Rejecting asks for a comment, because a rejection is final. *Why:* no dead buttons and no guessing; the rules explain themselves.

**Submit (builder's screen).** _(Updated in #15: the rationale is now required.)_ A form for the name, description, template, visibility, practice and rationale. The `{{variables}}` found are listed as you type, and the rationale box asks "Why did you build it this way?". After submitting, the builder sees the same rule flags and AI advice as the approver, plus "Flags don't block submission: a person reviews every tool". *Why:* builders fix problems early, so approvers get cleaner submissions.

**Catalog.** Published tools this persona may see, with visibility label, owner and rationale. "Personalise" fills in the blanks for your own copy. *Why:* approvers see what their approvals published, and users see why each tool exists before reusing it.

**Back-end support:** both changes this design needed are built: Specialists opening the queue (option A), and routing to one or more areas with each tool's own step list (#11). Tool details include `steps` for the progress line.

---

## 11. Route one tool through one or more specialist areas, in order

**Decision (2026-11-16):** at step 1 the Super admin picks **one or more** specialist areas, in order. Each chosen area becomes its own review step, so every routed tool gets its own list of approval steps: route → review (area 1) → review (area 2) → … → publish. Built now, before the front end. This extends #1, which allowed one area.

**Rules:** reviews happen strictly in the chosen order, and only a specialist from that step's area can decide it. Each specialist must be a different person from whoever decided any other step. No self-approval at any step, for anyone. A rejection at any review ends the review. An area can't be picked twice, and at least one area is needed.

**Older tools keep working:** a tool routed before this change has no step list of its own. It carries on with the shared three-step list and its single area. A routed tool's own list is fixed: later changes to the shared list don't affect it.

**Why:** some tools need more than one kind of expert, for example compliance *and* marketing. Each review is its own visible step, so the progress line (#10) shows exactly who has checked the tool and who hasn't.

**Trade-off:** the areas are chosen up front, in a fixed order. The Super admin can't add another area after seeing the first review. That's what's left of the "Hub-and-spoke routing" backlog item.

---

## 12. Front-end technology, the reject-comment rule, and browser tests

**Decisions (2026-11-16):**

1. **Plain HTML and JavaScript, served by the existing FastAPI server.** No framework and no build step.
   - **Why:** nothing new to install, one command starts the app, and the pages and API share one address, so there's no cross-site setup. The code stays short and readable for three screens.
   - **Trade-off:** shared pieces (the progress line, the persona dropdown) are plain functions rather than reusable components, and keeping the screen in step with the data is done by hand. That gets harder as screens and live updates grow. "Move the front end to React" in BACKLOG.md says when to switch.

2. **The back end refuses a rejection without a proper comment.** Not just the screen.
   - **The rule:** the comment must be at least 10 characters once spaces around it are ignored. Empty, spaces-only and shorter comments are refused. The API answers with this plain-language message and says it belongs to the comment box (`"field": "comment"`), so the screen shows it right next to the box, not as a bare error code: *"Add a comment of at least 10 characters explaining why you're rejecting this tool. The builder will see it."* The "who may act" checks still come first, so the tool's owner is told "your own tool", not "comment too short".
   - **Why:** a rejection is final, so the builder needs to know why. If only the screen asked, anyone calling the API directly could skip it. Putting the rule in the back end means it holds everywhere and is tested in Python.
   - **Trade-off:** a reviewer can't reject in one click, and existing calls that reject without a comment now get a 400 error. Ten characters stops empty or "no" comments, but not unhelpful ones; reviewers still need to write something useful.

3. **No automated browser tests (Playwright) for now.** The approval rules and the "can I act / why not" logic live in the back end and are tested in Python. Each page gets a test that it loads, and the screens are checked by hand as each persona.
   - **Why:** Playwright needs a large browser download and about 30–45 minutes to set up. The risky logic is already tested, and the screens are mostly display.
   - **Trade-off:** a broken button or a display mistake won't be caught automatically, only by hand. "Browser tests (Playwright)" in BACKLOG.md covers adding them later.

4. **Every rejected tool shows a clear "Rejected" note:** who rejected it, when, at which step and their reason. Each tool's details include it as `rejection`. The note appears on the builder's view of the tool (their tool page and "My tools") and in the Review queue detail panel, next to the progress line.
   - **Why:** the builder learns exactly what to fix, and reviewers see where and why a review ended without reading the whole history.
   - **Trade-off:** rejected tools leave the Review queue, because it lists tools still in review. So the detail panel shows the note right after the reviewer rejects, and afterwards through the tool's page. A "recently decided" view in the queue would need its own filter.

---

## 13. Least privilege for Specialist reviewers and Practice admins

**Decision (2026-11-16):** a Specialist reviewer can view a tool's details (and its history) only if:
- its current step is a review for their area, or
- they already decided a step of that tool (approved or rejected).

Otherwise they're refused with a plain message: *"This tool isn't waiting for your area's review."*

**What doesn't change:**
- **Admins:** Practice and Super admins still see every tool in review.
- **Owners:** always see their own tools.
- **Published tools:** anyone sees them, following the catalogue's visibility rules.
- **The Review queue:** it already showed Specialists only their own area's waiting work (#10).

**Why:** people should see only what their job needs (*least privilege*). A tool in review can hold unpublished wording, rule flags and the AI's notes. A Specialist needs those for their own review, not for tools that never come to them.

**Trade-off:**
- **No looking ahead:** a Specialist can't preview a tool before it reaches their step. For example, marketing can't see a tool that's still with compliance.
- **No wider context:** a Specialist can't look at tools that were never routed to them, even out of curiosity or for consistency. They have to ask an admin.
- **More to test:** the rule depends on where each tool is in its review, which makes it a little harder to reason about than "reviewers see everything".

### Practice admins (added 2026-11-16)

**Decision:** a tool belongs to **its owner's practice**. A Practice admin sees only their own practice's tools, in the Review queue and in tool details (and history). For any other tool they're refused with: *"This tool belongs to another practice."*

**What doesn't change:**
- **Super admin:** still sees every tool from every practice.
- **Owners:** always see their own tools.
- **Published tools:** anyone sees them, following the catalogue's visibility rules. So a firm-wide published tool from another practice is still visible to a Practice admin.

**Why the owner's practice:** most tools don't name a practice. A tool's own "practice" field is only filled in for practice-only tools, and 4 of the 5 sample tools leave it empty. Every builder has a practice, so going by the owner always gives an answer.

**Why:** Practice admins review what their own practice builds and decide no approval step. Other practices' unpublished tools, rule flags, AI advice and reviewer comments aren't theirs to see.

**Trade-off:**
- **Tools with no practice:** a tool whose owner has no practice (for example a Specialist's or the Super admin's own tool) is seen by no Practice admin, only by the Super admin, the owner and the Specialists reviewing it.
- **Moves between practices:** if a builder moves to another practice, their tools in review move with them to that practice's admin.
- **Lost overlap:** a Practice admin can no longer spot that another practice is building the same thing. The "Spot overlap" backlog item would bring that back as a summary only, without the review details.

---

## 14. The Catalog screen and personalising

**Decisions (2026-11-16):**

1. **The back end gives the Catalog everything it shows:** for each published tool this persona may see, the owner's name, a visibility label ("Firm-wide" or "Practice-only: Tax"), the description, rationale and template, and the **blanks** to fill in, each with an on-screen label ("client_name" becomes "Client name"). Rule flags, AI advice, steps, history and reviewers' comments are left out of the catalogue.
   - **Why:** the screen only displays. Reviewing details belong to reviewing, and tool users shouldn't see reviewers' internal comments (see "Update a published tool" in BACKLOG.md).

2. **The blanks come from the template itself,** not from the builder's declared list. Personalising fills what the template actually uses, so the form asks for exactly those.
   - **Why:** if the two lists disagree (the `variables_match` check flags this, but flags don't block publishing), the form and the download still match.

3. **The back end refuses unusable values,** with a plain message and a `fields` list naming the boxes, so the screen marks those boxes: *"Fill in every blank before downloading your copy: Client name."* Empty and spaces-only values count as missing. A value for a blank the tool doesn't have is refused too. "Who may use this tool" is checked first. The page has no browser-side checks of its own.
   - **Why:** the rule holds for anyone calling the API, not just the screen, and it's tested in Python.

4. **Personal copies are never saved.** The values someone types may be client details, so they're used for that one copy, returned to the browser, and forgotten. A test checks that the database is unchanged afterwards. The download's file name comes from the tool's name only ("meeting-summary.txt"), never from the values.
   - **Why:** templates stay clean (BRIEF.md), and file names get seen in download folders and email attachments.
   - **Trade-off:** there's no "my copies" list. If someone loses their file, they fill in the blanks again.

5. **The sample data publishes nothing,** so on a fresh start the Catalog says no tools are published yet. To see it working, take a seeded tool through the three approval steps first.
   - **Why not seed a published tool:** it would change the seeded tools, which means refreshing the sample AI advice (paid AI calls) and changing several tests' expectations. That's worth a separate decision.

---

## 15. The Submit screen, and a required rationale

**Decisions (2026-11-16):**

1. **The rationale is required to submit.** The back end refuses a submission with an empty or spaces-only rationale: *"Explain why you built it this way."*, shown next to the rationale box. This holds on the Submit screen (`POST /submissions`) and on a direct `POST /tools/{id}/submit`. A draft can still be saved without one. The "who may submit" checks come first, and a refused submission makes no AI call.
   - **Why:** the rationale is the tool's record of why it was built this way (BRIEF.md, "lost reasoning"). Before, an empty one was only flagged, so a tool could reach reviewers with no reasoning at all, and reviewers had to ask for it. Refusing it at the door is cheaper for everyone. Putting the rule in the back end means a direct API call can't skip it.
   - **What stays a flag:** a rationale that's present but too short (under 20 characters, such as "n/a") is accepted and flagged by `has_rationale`, as before. Flags never block: a person reviews every tool. The line is "is there any reason at all?" (refused) versus "is it a good one?" (a person and the AI judge).
   - **Trade-off:** this changes #7 a little. An empty rationale is no longer just a flag; it's refused. Someone can still type "n/a" to get past the refusal, but that's flagged for the reviewer.

2. **The seed's sample submissions are exempt.** "Client welcome letter" keeps its empty rationale, so the demo still shows the `has_rationale` flag. The seed loads it with sample advice, which only the seed can pass (a test guards this), so it stands for a submission made before this rule.
   - **Why not change it to "n/a":** the rationale is part of each seeded tool's fingerprint, so changing it means refreshing the sample AI advice (paid AI calls, on Vanessa's say-so).
   - **Trade-off:** the demo shows a tool that couldn't be submitted today. If that matters, change its rationale to "n/a" and refresh the sample advice.

3. **The back end describes the form.** `GET /submit-form` lists each box with its label, a short hint, and whether it's `required`. A test checks that the boxes marked required are exactly the ones the back end refuses when empty. It also lists the visibility choices (each saying whether it needs a practice), the practices, the persona's own practice to start with, and the 20-character rationale minimum.
   - **Why:** the "Required" marks and the refusals can't drift apart, and the page holds no rules.

4. **The screen marks and explains, the back end decides.** Required boxes show an asterisk and a "Required" tag, with a note at the top: "Fields marked * are required." Each box has a hint underneath. On a refusal, the back end sends one message per box (`messages`), and the page shows each next to its box. The page doesn't use the browser's own `required` checks, because they would stop the form before the back end's message could be shown. Screen readers still hear "required" (`aria-required`).

5. **One call creates and submits.** `POST /submissions` checks everything first, reporting every problem at once, and only then saves and submits. A refusal saves nothing.
   - **Why:** with two calls (save the draft, then submit), a refused submit would leave a stray draft behind.

6. **After submitting, the builder sees what the approver sees, explained.** First a confirmation ("Submitted for review"), and "Flags don't block submission: a person reviews every tool". Then **Rule flags**: each one in plain words with a **tip for next time** from the back end. Then **AI advice: you decide**: a one-line summary, the issues and the reason, labelled when it's sample advice. Last, **what happens next** (whose turn it is).

7. **The blanks are found by the back end as you type** (`POST /templates/blanks`, which saves nothing). The tool's declared list comes from the template too, so the `variables_match` check always passes for tools made on this form.

8. **Firm-wide tools store no practice.** The back end drops a practice sent with a firm-wide tool, and trims or empties the practice otherwise. So the page doesn't need to know which visibility uses a practice. It shows the Practice box only when the back end's `asks_practice` says so.

---

## 16. The AI shouldn't flag a missing practice (2026-11-17)

**Decision:** one sentence added to the end of the "Otherwise mark safe" paragraph of the agent's instructions (`SYSTEM_PROMPT`): *"Visibility and practice aren't risks: a firm-wide tool has no practice, and a missing practice on a practice-only tool is caught by a separate check."*

**Why:** a real review listed "Practice field is null" as an issue for a firm-wide tool, which has no practice by design (#15, point 8). An exact copy of that tool reproduced it in 9 of 10 runs. With the sentence: 0 of 10, and the full eval (run 5) still got every judged answer right. Practice-only tools without a practice are already flagged by the rule-based `practice_set` check, so the AI doesn't need to judge it.

**Why not the wider wording** ("list only issues that match the six rules"): it would also stop notes such as "the name is a placeholder" or "the description is empty", which reviewers may find useful. That's a bigger change in behaviour than this problem needed.

**Trade-off:** the instructions are about 35 tokens longer (about $0.000004 per review), and the sample advice had to be refreshed. The trigger seems to be a submission that looks like an unfilled form, so other "field is empty" issues may still appear for those. They're advice only.

---

## 17. The AI's reply limit is 1,000 tokens (2026-11-17)

**Decision:** `MAX_TOKENS` in `registry/agent.py` went from 8,000 to 1,000. It caps how long the AI's reply may get, its thinking included.

**Why:** in eval run 5, one reply ran away to the 8,000-token limit: 22 seconds and $0.004 before it was cut off. A cut-off reply already becomes "needs a human", so the limit only decides how long and how costly a runaway is before a person takes over. At 1,000, that's about 3 seconds and $0.0005, inside the 10-second target. Real replies use about 120 tokens, and the longest of about 580 eval calls was 386, so 1,000 is about 2.6 times that.

**Safeguard:** a test fails if the limit is ever less than twice the longest completed reply in the saved eval results.

**Trade-off:** an unusually long genuine reply would be cut off and sent to a person, not lost. The old limit left "room for the model's thinking". At effort `medium` the model's output has stayed under 400 tokens, but a higher effort level could need more, so rerun the eval after raising it. Not rerun with real calls when the limit changed, because normal replies aren't affected.

---

## 18. How the Review queue screen asks and displays (2026-11-17)

**Decision (Vanessa's answers to the step 6 plan):**
1. **Routing order:** one checkbox per area; the order is the order they're ticked, shown as 1, 2, 3. Unticking moves the later ones up. Chosen over "Move up / Move down" buttons: simpler, and nothing to drag.
2. **Publish defaults:** visibility and practice start from what the builder asked for, so the Super admin usually just confirms.
3. **Shared display code:** the rule flags, the AI advice and the progress line are drawn by one copy in `web/app.js` (`renderFlags`, `renderAdvice`, `renderProgress`), used by both the Submit page and the Review queue, so the two can't drift apart.
4. **Empty "Waiting on me":** "Nothing is waiting on you." with a "Show all in review" button. Practice admins never decide a step (#13), so they always see this first; no new rule was needed.
5. **Readable wording:** text the screens show uses the names in the persona dropdown ("the Super admin", "a Compliance specialist", "Firm-wide"), including refusal messages. Tests that checked the old wording expect the new text and are as specific as before.

**How this keeps rules out of the screen (#12):**
- The back end sends the **choices** for each decision (`my_action.choices`): the areas when routing, and the visibility options, practices and builder's request when publishing. The page has no list of its own.
- "Waiting on me" is the back end's `my_action.can_decide` per tool. A test checks, for every persona at every stage of a review, that it's true exactly when the decision would be accepted.
- The page checks nothing a person types or picks; the back end's message appears next to the comment box or the buttons.
- Stored history records stay as written; the back end adds a readable `detail_label` for the screen.

**Trade-off:** the back end carries a few display-only fields (`choices`, `detail_label`, `status_label`, `owner_name`). They're cheap, and they keep wording and rules in one place.

---

## 19. Tool users can't submit tools (2026-11-18)

**Decision:** Tool users only use published tools. The back end refuses them when they load the Submit form, save a draft or submit, with "Tool users can't submit tools. You can use the published tools in the Catalog." Nothing is saved. The navigation hides "Submit a tool" for them, using a `can_submit` flag the back end sends with each persona, the same way the Review queue link uses `can_open_queue`.

**Why:** found in the by-hand check of step 6. The link was shown to everyone, and the back end didn't refuse: a Tool user could save and submit their own tool. Only the owner check stopped them submitting someone else's.

**Who can submit:** Builders, and also admins and specialists (`SUBMIT_ROLES` in `registry/personas.py`). The request was "only Builders submit", but the approval rules already expect admins and specialists to build tools ("nobody approves a tool they own, admins included", #7), and tests rely on it. So only Tool users were taken out. Limiting it to Builders alone would be a one-line change to `SUBMIT_ROLES`, plus the tests that use admin- or specialist-owned tools.

**Confirmed by Vanessa (2026-11-18):** keep it this way. Only Tool users are blocked from submitting. Admins and specialists can still submit, and the no-self-approval rule still covers them: they can't approve or reject a tool they own. The test change below (a made-up Audit builder instead of Jamie) is also confirmed.

**Safeguards:** a test checks, for every persona, that `can_submit` matches whether a real submission is accepted. Another checks that a Tool user's draft saved before this rule can't be submitted.

**Test change:** the least-privilege tests used Jamie Larkspur, a Tool user in Audit, as the owner of an Audit-practice tool. They now add a made-up Audit builder ("Casey Example") instead, the same way they already add a made-up Audit admin. What they check is unchanged.

**Later:** "Let anyone propose a tool" (BACKLOG.md): whoever submits becomes the builder.

---

## 20. Fixes from the by-hand check of the Review queue (2026-11-18)

All 11 checks passed. These changes followed:

1. **No screen shows "null".** The browser's `replaceChildren()` shows an empty value as the word "null" (no rejection and no description gave "nullnull"). A shared `fill()` in `web/app.js` skips empty values the way `h()` does, and every page uses it. A guard test fails if any page puts content on screen another way. A missing date now shows nothing, not 1 January 1970.
2. **On a phone, picking a tool scrolls to its details** and moves focus to their heading. The page works out whether the details sit below the list from where they are on screen, so it follows the stylesheet without a second copy of its breakpoint. The scroll is instant for people who prefer reduced motion.
3. **After a decision, say who's next.** "It has left the queue" was confusing after a specialist approved, because the tool was still in review. Now: "It has left your queue and is now waiting for the Super admin.", or "It's now waiting for …" when it's still in your queue. Finished tools say "This tool is now: Published. It has left the review queue."
4. **"Published. Nothing left to decide."** replaces "This tool is already published.", which read like an error after a successful publish.
5. **"Skipped: rejected at step N"** replaces "Not reached" on the progress line. The back end sends it as `skipped_reason`; the status code stays `not_reached`. Once fix-and-resubmit exists, it becomes "On hold: waiting for the builder to fix and resubmit" (BACKLOG.md).
6. **US wording:** "select" and "clear" instead of "tick" and "untick" on every screen, checked by a test. #18 keeps its original wording as a record of what was decided then.
7. **Tool users can't submit** (#19).
8. **The start command** in STATUS.md was wrong (`registry.api:app`); it's `.venv/Scripts/python -m uvicorn registry.api:create_app --factory --reload`. A test checks every doc.

**Still to do** (BACKLOG.md "Design polish", before the README screenshots): line up the Review queue's empty views, and hide "Pick a tool" when there's nothing to pick.

---

## 21. Design polish and the fixes after its check (2026-11-18)

**The progress bar (from BACKLOG.md "Design polish"):** the progress line is one connected bar, on the Submit page and in the Review queue (one shared `renderProgress` in `web/app.js`). Each step is a circle with a symbol as well as a colour: ✓ done, ● now, ✕ rejected, – skipped, an empty circle for later. A line joins the circles and turns green up to the last done step. The symbols are hidden from screen readers, which still hear each state in words. Only the screen changed: the back end's `steps` are as before.

**Side by side or stacked:** the steps sit side by side when their box is at least 34rem wide, and stack down the page otherwise (phones). The width is measured on the progress bar's own box (a CSS container query), not the whole window, so the same rule works in the wide Submit page and the narrow queue details box.

**More than 3 steps in the queue's details box stack** (your fix after the browser check). That box is about 35rem wide on a desktop, so 4 or 5 steps side by side squeezed the dates onto 3–4 lines. The stylesheet counts the steps the back end sent; the page works nothing out. The Submit page is wide enough and keeps 5 steps side by side.

**The empty Review queue:** when the list being shown is empty, the "Pick a tool to see its details." box is left out and the empty message uses the full width. When a just-decided tool is still shown beside an empty list, the two boxes' tops line up.

**The publish confirmation says where the tool went** (your fix): "Decision recorded. Published firm-wide. It has left the review queue." or "… Published to the Tax practice only. …". The back end sends the words as `published_label` (empty until a tool is published), from what was actually published, which may differ from what the builder asked for. The page doesn't read the visibility itself, keeping #12's rule that screens only display what the back end says.

**Added to the backlog, not built:** "Confirm AI advice" (a specialist selects the AI points they agree with as their reason, shown as the person's decision; agreement rate and decision time tracked against rubber-stamping) and "Require a reason to approve against the AI's advice".

---

## 22. Fixes from the Codex review (2026-11-18)

The findings, who found them and their status are in REVIEW.md. One commit per fix, each with tests written first.

**Finding 1: only practices from the list.** A practice-only tool's practice must be one of the practices people belong to (`practice_names`: Audit and Tax in the demo). This is checked when a tool is saved or submitted, and when the Super admin publishes it as Practice-only. Anything else is refused with "Choose a practice from the list: Audit or Tax.", next to the Practice box, and nothing is saved. Unchanged: a blank practice is still saved and flagged by the checks, not refused, and a firm-wide tool ignores the practice box. The screens already offered only listed practices, so this closes the gap for direct API calls. Once admins keep the practice list (BACKLOG.md "Admin-managed practice list"), the check reads from that list instead.

**Finding 2: someone not in the registry can't save or submit.** `check_can_submit` now refuses an unknown person ("Only people in the registry can save or submit tools.") before anything else runs: no save, no checks, no AI call. Before, it let them through, and only other checks stopped them: the API's persona check, then the database's owner link (as a crash, not a plain message) or the owner-only submit check. Those stay as extra layers. **Test change:** `test_unknown_owner_refused_by_database` now checks the database's own refusal with a direct insert, because `create_tool` no longer reaches the database for an unknown owner. What it checks is unchanged.
