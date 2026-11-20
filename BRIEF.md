# Tool Registry: Project Brief

## Problem
AI tools are spreading faster than the rules for managing them. That causes five problems:

1. **No review before clients see it.** Tools can reach clients before anyone has checked them.
2. **Data leaks.** When a tool is shared, the workspace it was built in can go with it, including any data in that workspace.
3. **Wasted spend.** Teams build the same tool twice. Tools also run inside AI apps when a pre-built version would cost almost nothing.
4. **Orphaned tools.** When the people who built them leave (interns, for example), nobody owns the tools anymore.
5. **Lost reasoning.** People edit templates by hand, and nobody remembers why they were built the way they were.

## Solution
One governed catalog. Each tool is reviewed once, as a template ("review once, reuse many times"). Templates are stored clean, with no client data. Each one keeps a short record of why it was built that way. Users then make their own copy and personalize it.

## Users
- **Builder:** creates and submits tools.
- **Practice admin:** reviews tools submitted from their practice and decides what goes in that practice's library. _(In the built demo, Practice admins became read-only viewers of their own practice's tools and decide no approval step; see DECISIONS.md #13.)_
- **Super admin:** sends submissions to the right specialists and decides whether a tool is for one practice only or the whole firm.
- **Specialist reviewers** (compliance, marketing, technology): review their part and escalate to AI enablement (technology) when needed.
- **Tool user:** finds approved tools and personalizes them.

## Hypothesis
An AI pre-review plus a clear approval path will cut review time without missing risks.

## Success Metrics
- Catches **every** risky submission in the test set.
- Correctly passes **at least 80%** of safe submissions. Anything flagged goes to a human; nothing is auto-rejected.
- Costs **under 1 cent** per review.
- Returns a result in **under 10 seconds**.

## Out of Scope
- Real client data or real systems
- Real sign-in (a persona dropdown is used instead)
- Separate libraries for each practice
- Cost/ROI dashboard
- Live hosted demo
