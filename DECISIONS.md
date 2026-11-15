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
