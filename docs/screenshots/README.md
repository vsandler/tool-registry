# Screenshots for the README

Each image here is a gray placeholder. Replace it with a real screenshot **of the same file name**, so the README needs no changes. Suggested size: a desktop browser window about 1600 × 900, at 100% zoom.

**Before you start**
- Delete `registry.db` and start the app, so you begin from the clean sample data.
- Screenshot 2 makes one real AI call (well under 1 cent), so it needs your own API key in `.env`. The others need no key.
- Keep the persona dropdown in view in every shot, so the reader can see whose eyes they're looking through.
- Only the made-up sample data should be on screen: no real names, emails, browser bookmarks, tabs or account details.

| # | File | Screen | Persona | What should be visible | Setup |
|---|---|---|---|---|---|
| 1 | `01-hero-review-queue.png` | Review queue, a tool selected | Riley Ashgrove (Super admin) | "Client welcome letter" open: the progress bar on step 1 (Route), **Rule flags** showing its four flags (client data, blanks don't match, no reason recorded, no practice named), **AI advice: you decide** marked *risky* with its issues and the "Sample advice" label, and the routing choices | None: it's in the queue on a fresh start |
| 2 | `02-submit-ai-advice.png` | Submit a tool, after submitting | Avery Quill (Builder) | The "Submitted for review" confirmation, "Flags don't block submission", all rule checks passing, and the **AI advice** flagging the promise that savings "will steadily grow faster than inflation" | Copy the "Savings check-in note" draft's text into the Submit form (change the name slightly, e.g. "Savings check-in note v2", so the unique-name check passes) and submit. Real AI call. |
| 3 | `03-routing.png` | Review queue, routing step | Riley Ashgrove (Super admin) | "Meeting summary" selected, with **Compliance** and **Marketing** selected and numbered **1** and **2**, before clicking the button | None |
| 4 | `04-cannot-act.png` | Review queue, a tool you can't decide | Sam Thistle (Compliance specialist) | After Sam approves the compliance step of "Meeting summary": the progress bar with step 2 done (✓) and step 3 waiting, and the plain message that it's now waiting for a Marketing specialist, with no decision buttons | Route "Meeting summary" to Compliance then Marketing (shot 3), then approve it as Sam |
| 5 | `05-rejection.png` | Review queue, just rejected | Quinn Harrow (Marketing specialist) | The **Rejected** note (who, when, which step, the comment) and the progress bar with ✕ at the marketing step and the publish step "Skipped: rejected at step 3" | Continue from shot 4: as Quinn, reject "Meeting summary" with a made-up comment such as "Please add the standard disclaimer before the summary." |
| 6 | `06-catalog-personalize.png` | Catalog, Personalize form | Jamie Larkspur (Tool user) | A published card with its "Firm-wide" label, owner and rationale, and the Personalize form with every blank filled with made-up values | Publish "Engagement letter draft" first: as Riley, route it to Technology; as Devon Marsh (Technology specialist), approve; as Riley, change the visibility to **Firm-wide** and publish (the builder asked for Tax only, and Jamie is in Audit, so a Tax-only tool wouldn't show for Jamie). Then switch to Jamie. |
