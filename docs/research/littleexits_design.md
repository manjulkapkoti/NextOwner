# LittleExits.com — Architecture & Design Research

> Research date: **13 July 2026** · Fourth site in the series (Acquire → Baton → Exitwise → this).
> Method: HTML/bundle inspection of both the marketing site and the logged-in app, Next.js build-manifest route enumeration, header analysis, web search. Marked **(inferred)** where not directly observed.
> Verdict for NextOwner: see §6.

---

## 1. What Little Exits Is

Little Exits (formerly **Tiny Acquisitions**, founded 2021 by [Stephen Campbell](https://littleexits.com/about), rebranded April 2024) is the acquisition marketplace for **indie hackers** — side projects, micro-SaaS, newsletters, communities, and "things you built and moved on from," mostly **under $100k**. Claims: 25,000+ users, 750+ verified projects.

**Why it matters most to NextOwner:** of the four companies researched, this is the closest comparable — a self-serve marketplace at the *micro* end, built and run by a tiny team. It's proof that NextOwner's MVP scope is a real, operating business — and its architecture ("Acquire, one size smaller") independently converges on the same patterns.

### Business model

| Side | Revenue |
|---|---|
| Buyers | **Premium ~$249/yr** — full analytics, direct messaging, offer-making (free tier: browse with limited filters) |
| Sellers | Listing fees hinted in FAQ; optional **broker service** (`/broker`) for assisted sales |
| Deal flow | Offer → accept → **invoice generated** → payment with escrow protection → **built-in asset transfer ("exchange")** |

The four-company spectrum is now complete: Little Exits (micro, self-serve) → Acquire (SMB-digital, self-serve+) → Baton (main-street, hybrid) → Exitwise (upper-mid, pure human advisory). Software's share of the work shrinks as deal size grows.

---

## 2. Tech Stack

### 2.1 Verified by direct inspection

| Layer | Technology | Evidence |
|---|---|---|
| Marketing site (`littleexits.com`) | **Next.js** (pages router, fully static export — `nextExport: true`) | `__NEXT_DATA__`, build manifest |
| Product app (`app.littleexits.com`) | **Separate Next.js app**, also static-exported shell, client-side data | Own buildId, `/search`, `/dashboard`, `/login`, listing pages at `/tiny/{slug}` |
| Hosting | **Vercel** for both (first Vercel deployment in this research series) | `Server: Vercel`, `X-Vercel-Cache`, Speed Insights script |
| Backend | **Firebase** — project `little-exits`: Firebase **Auth** (`securetoken.google.com`) + **Realtime Database** (`little-exits-default-rtdb.firebaseio.com`); Firestore possible but not directly observed | Firebase SDK config in app chunks |
| Payments | **Stripe** | 28 signatures in app chunk |
| Abuse protection | **reCAPTCHA Enterprise** | `recaptcha/enterprise.js` |
| Data fetching | SWR | Signature in chunks |
| Styling | **Tailwind CSS** | Signatures |
| Analytics | **Plausible** (privacy-friendly) + GA/gtag + Segment + Vercel Speed Insights | Scripts + signatures |
| Monitoring | Sentry (light traces) | 3 signatures |
| Misc | Typekit fonts, ipapi.co (visitor geo), Iconify SVG APIs | Bundle URLs |

### 2.2 Notable architecture facts

- **"Acquire, one size smaller":** Next.js/Vercel frontend + Firebase BaaS + Stripe — the same buy-don't-build philosophy as Acquire.com, with an even thinner stack. Two of the four researched marketplaces independently chose Firebase.
- They use the older **Realtime Database** (Acquire's legacy component) as a primary datastore rather than Firestore — a reminder that at this scale, "whatever ships" beats "whatever's newest" **(inference from observed RTDB URL; Firestore may also be in use)**.
- The marketing site and app are **separate Next.js deployments on separate (sub)domains** — the subdomain pattern (like Acquire), not the path-zone pattern (like Baton/Exitwise).
- Escrow at micro price points appears to be handled **in-platform via Stripe** rather than Escrow.com **(inferred)** — Escrow.com economics don't work on a $500 side project.

### 2.3 Architecture sketch

```
littleexits.com (Vercel)                 app.littleexits.com (Vercel)
Next.js static export                    Next.js app (client-rendered data)
· homepage, pricing, /forbuyers          · /search  /dashboard  /login
· /apps mini-tools suite                 · listings at /tiny/{slug}
· /broker  /ownership                    · offers · messaging · invoices
        │                                        │
        └── Plausible · GA · Segment ────────────┤
                                                 ▼
                                   Firebase (BaaS on Google Cloud)
                                   Auth · Realtime Database · (Storage)
                                   + Stripe (payments/premium)
                                   + reCAPTCHA Enterprise (abuse)
```

---

## 3. Product Features Observed

- Marketplace: search/filters (premium-gated depth), verified metrics, listing pages, saved-criteria **notifications**, in-app messaging (premium), offers.
- Deal completion: offer acceptance → **invoice generation** → escrow-protected payment → **built-in asset-transfer flow**.
- Valuation guidance from the platform's **own sales comps**.
- `/apps` — a suite of free mini-tools: **invoice generator**, **NotBehind** (monitoring), **palette**, **webhooks**, **quit**. Lead magnets for the exact indie-hacker audience.
- `/broker` — optional human-assisted selling upsell; `/ownership` — ownership/verification content.
- Buyer premium at $249/yr gating messaging + offers (the "serious buyers only" filter, same logic as Acquire's paid tiers).

---

## 4. Cool Features Log (Little Exits)

*(Also recorded in [`cool_features.md`](./cool_features.md).)*

1. **Free mini-apps suite (`/apps`)** — five tiny free tools for indie hackers (invoice generator, uptime monitor, palette, webhooks tester). Lead magnets that *are* products — each earns links and signups from exactly the audience that later lists projects.
2. **Invoice generation on offer acceptance** — at micro deal sizes there's no lawyer; the platform generating the payment artifact keeps the transaction on-platform and legible.
3. **Built-in asset-transfer "exchange"** — the handover (domain, code, accounts) is a first-class product flow, not an off-platform afterthought. Validates NextOwner's mocked transfer state machine as a real feature direction.
4. **Comps-based valuation guidance** — pricing suggestions from the marketplace's own historical sales. Independent validation of `agentic_scope.md` proposal F (proprietary comp corpus as moat).
5. **Premium-gated messaging/offers ($249/yr)** — the paywall sits exactly on the *connection* moment, same as Acquire — third confirmation that "gate the contact, not the browsing" is the standard monetization for this category.
6. **Optional `/broker` upsell** — self-serve by default, human help as a product tier: the Baton/Exitwise spectrum compressed into one feature.

---

## 5. Trust & Safety Observations

- reCAPTCHA Enterprise on the app (their App-Check analog).
- "Verified projects with real metrics" as the core marketing claim — verification is the product across all four researched companies, at every deal size.
- Escrow protection marketed even at micro scale — trust machinery is non-negotiable no matter how small the deal.

---

## 6. Relevance Verdict for NextOwner

### Adopt now
Nothing — no spec, data-model, or architecture changes. (Same result as Exitwise, but for the opposite reason: not because it's irrelevant, but because NextOwner's plan already matches what Little Exits proves works.)

### Strong validations (no action, more confidence)
- **The MVP scope is a viable business** — a near-identical product (browse → gate → message → offer → invoice → transfer) runs profitably at the micro end with a tiny team.
- **Monetization placement** — the third company gating messaging/offers behind a buyer subscription (~$249–$390/yr) confirms `acquire_design.md` FR-19's post-MVP plan.
- **Firebase twice** — two of four marketplaces chose BaaS; NextOwner's FastAPI choice remains a deliberate learning trade-off, well-documented in the constitution.

### Adopt later (post-MVP backlog)
| Idea | Where it fits |
|---|---|
| **Invoice generation on offer acceptance** | Natural M7 extension: `POST /offers/{id}/accept` also renders a simple invoice (HTML→PDF) attached to the deal record. Small, high-legibility win for micro deals. |
| **Asset-transfer checklist as first-class flow** | Upgrade the mocked escrow/transfer buttons into a checklist state machine on the deal (domain ✓ code ✓ accounts ✓) — pairs with the Deal-Room Orchestrator agent (proposal E). |
| **Free mini-tools as lead magnets** | The `/apps` pattern generalizes M11's calculator into a suite; each tool targets the seller audience (e.g., MRR screenshot beautifier, TTM profit calculator). |
| **Plausible analytics** | When `track()` gets a real backend, Plausible is the privacy-friendly, cheap default worth considering before Segment-class tooling. |
| **reCAPTCHA/abuse protection on auth** | Production-hardening item alongside rate limiting (constitution Article 2 note on App Check equivalents). |

### Explicitly do NOT copy
- **Realtime Database as primary datastore** — works for them, but it's legacy tech; NextOwner's SQL choice is strictly better for marketplace queries.
- **Two separate frontend deployments on subdomains** — NextOwner already adopted the single-origin path layout; no reason to regress.

---

## 7. Sources

- [littleexits.com](https://littleexits.com/) + [about](https://littleexits.com/about) — HTML, build manifest, bundles
- [app.littleexits.com](https://app.littleexits.com/search) — app shell + chunk inspection (Firebase config, Stripe, reCAPTCHA)
- [Tiny Acquisitions rebrands to Little Exits (Smart Branding)](https://smartbranding.com/tiny-acquisitions-rebrands-to-little-exits-the-acquisition-marketplace-for-indie-hackers/)
- [Rebrand announcement (their newsletter)](https://newsletter.littleexits.com/posts/tiny-acquisitions-is-rebranding-to-little-exits)
- [Little Exits on X](https://x.com/LittleExits)
