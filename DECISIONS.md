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

## 4. Start the AI agent on Claude Haiku 5.5

**Decision:** The AI pre-review agent starts on Claude Haiku 5.5.

**Why:** It's fast and cheap, which fits the targets of under 1 cent and under 10 seconds per review.

**Trade-off:** A smaller model might miss risks that a larger one catches. Before we commit, we'll run Haiku 5.5 and Sonnet 5.5 through the same evals (the test set of safe and risky submissions) and choose based on the results.

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

**Decision:** The eval runs every case 3 times. A risky case counts as caught only if it's flagged in all 3 runs. A safe case passes only if it's clean in all 3 runs. Any case whose answer changes between runs is listed as inconsistent. The brief's "8 of 10 safe" target is applied as at least 80% in every run.

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
