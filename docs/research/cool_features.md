# Cool Features Log — Running Cross-Site Notes

> Features spotted during competitive research that are worth remembering for NextOwner. One line of *what*, one of *why it's cool*. Newest research first. (Requested: "make note of any cool feature that you come across.")

## From Little Exits (littleexits.com) — researched 2026-07-13

| # | Feature | Why it's cool / NextOwner takeaway |
|---|---|---|
| L1 | **Free mini-apps suite** (`/apps`: invoice generator, uptime monitor, palette, webhooks tester) | Lead magnets that ARE products — each earns links/signups from the exact audience that later lists projects. Generalizes M11's calculator into a suite (post-MVP). |
| L2 | **Invoice generation on offer acceptance** | At micro deal sizes there's no lawyer — the platform generates the payment artifact. Natural M7 extension (HTML→PDF on accept). |
| L3 | **Built-in asset-transfer "exchange" flow** | The handover is a first-class product step, not an off-platform afterthought. Upgrade path for NextOwner's mocked transfer state machine + proposal E agent. |
| L4 | **Comps-based valuation guidance** from their own sales history | Third validation of the proprietary-comps moat (`agentic_scope.md` proposal F). |
| L5 | **Premium-gated messaging/offers (~$249/yr)** | Third company gating the *connection* moment, not the browsing — confirms FR-19's post-MVP monetization placement. |
| L6 | **Optional `/broker` upsell** on a self-serve marketplace | Human help as a product tier — the Baton/Exitwise spectrum compressed into one feature. Future "guided" tier validation. |

## From Exitwise (exitwise.com) — researched 2026-07-13

| # | Feature | Why it's cool / NextOwner takeaway |
|---|---|---|
| E1 | **Exited Founders directory** — searchable gallery of ~70 real founders who exited, each with a profile page (Webflow CMS + Finsweet filtering) | Social proof + SEO + supply-side recruiting in one feature. NextOwner version: "Sold on NextOwner" success-story pages once deals close. |
| E2 | **Surgical engineering** — all no-code (Webflow/Tally/Calendly/Beehiiv) except ONE custom Next.js app, path-mounted at `/valuation-calculator` | Second independent validation of the path-zone/single-origin layout (§3.4) — and a lesson: spend engineering only where it differentiates. |
| E3 | **Exit-readiness quiz** (Tally.so embed) | Zero-engineering lead qualification: tells unready sellers what to fix, captures them for nurture. Pairs with M2's listing requirements as a pre-listing funnel. |
| E4 | **Intent-based SEO factory** — hundreds of posts targeting exact valuation queries ("dental practice valuation") | Content mapped to the moment of highest seller intent, all funneling into the calculator. Post-MVP marketing playbook. |
| E5 | **Dual conversion funnels** — separate booking flows for founders (`/call`) vs. exited founders joining the network (`/exited-call`) | The supply side deserves its own funnel — for NextOwner: distinct seller vs. buyer onboarding paths. |

## From Baton (baton.com) — researched 2026-07-13

| # | Feature | Why it's cool / NextOwner takeaway |
|---|---|---|
| B1 | **Elena — AI data-room analyst** answering buyer diligence questions **with document + page citations** | A competitor already shipped `agentic_scope.md` proposal C. Citation grounding turns "trust the AI" into "verify the AI" — copy that spec detail. |
| B2 | **Off-Market Profiles** — anonymous teasers for owners *not ready to sell yet*; buyers send informal offers | Supply-side growth hack: captures sellers years before they'd hire a broker. Post-MVP: an `off_market` listing status. |
| B3 | **One platform-wide NDA** (sign once, all gated listings) instead of per-listing NDAs | Huge buyer-friction reduction while keeping per-listing seller approval. **✅ Adopted 2026-07-13** into Milestone 5 / FR-13 / constitution Art. 4. |
| B4 | **Owner walkthrough videos** in listings | Cheap trust signal — a founder on camera beats ten paragraphs. Optional field in the listing builder (M2). |
| B5 | **Financial reconciliation before listing** — books validated pre-publication | "Verified" as the product, not a badge. The manual-curation version is NextOwner's M3; automated reconciliation is the agentic Trust & Vetting agent (proposal D). |
| B6 | **Public changelog + engineering blog** | Free marketing/recruiting/trust from work you'd document anyway. |
| B7 | **Path-based app zones on one domain** (`/`, `/baton-beat`, `/market/*`) | Deploy pattern: SPA + API under one domain = no CORS, shared cookies. **✅ Adopted 2026-07-13**: `/api` prefix + Vite dev proxy (§3.4) now, path-routed reverse proxy at deploy. |

## From Acquire.com (acquire.com) — researched 2026-07-13

| # | Feature | Why it's cool / NextOwner takeaway |
|---|---|---|
| A1 | **Metrics API sync** (ChartMogul/Metricable/Stripe) so listings show *verified* MRR/churn | Trust through data plumbing, not promises. Post-MVP integration; mock fixtures in MVP. |
| A2 | **Financial recasting** (`RecastFinancialList` flag) — normalized P&L across listings | Standardized data is the marketplace's real product; keep listing metrics structured (M2 lesson). |
| A3 | **Auto-signed NDA → instant data-room access** | The friction-killer Acquire optimizes; Baton's B3 is the next step of the same idea. |
| A4 | **Buyer verification tiers** (Persona KYC + proof of funds) surfaced as badges to sellers | Sellers triage buyers by signal, not vibes → milestone M10's manual version. |
| A5 | **Saved-search instant alerts incl. Slack** | Retention loop for buyers; email version is M8, Slack a cheap later add. |
| A6 | **Feature flags + maintenance mode baked into app config** | Operational maturity visible in the bundle; `flags.py` honors the same principle. |

---

*Add new sections above this line as more sites get researched.*
