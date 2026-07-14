# Exitwise.com — Architecture & Design Research

> Research date: **13 July 2026** · Third site in the series ([`../acquire_design.md`](../acquire_design.md) → [`baton_design.md`](./baton_design.md) → this).
> Method: HTML/bundle inspection (Cloudflare blocks generic fetchers with a 403 — a browser user-agent works), sitemap enumeration, embed detection, web search. Backend claims marked **(inferred)**.
> Verdict for NextOwner: see §6.

---

## 1. What Exitwise Is

Exitwise (Michigan; founded by exited entrepreneurs [Todd Sullivan and Brian Dukes](https://exitwise.com/about)) is **not a listings marketplace at all** — it's an **M&A advisory matchmaking service**. Founders who want to sell are matched with vetted, industry-specific investment bankers, M&A attorneys, and deal advisors, plus a mentor from a network of ~100 **exited founders** who "only get paid when the founder sells." They claim $4B+ in enterprise value guided.

### The three-company spectrum this research now covers

| | Acquire.com | Baton | Exitwise |
|---|---|---|---|
| What it is | Self-serve **software marketplace** | Marketplace + **tech-enabled brokerage** | **Pure advisory service** with a lead-gen site |
| Software's job | IS the product | Half the product | Marketing funnel for a human service |
| Listings? | Yes, thousands | Yes, curated | **No listings at all** |
| Deal execution | Templates + self-serve | In-platform + advisors | Entirely human (bankers/attorneys) |
| Engineering investment | Heavy (Firebase platform) | Heavy (custom AWS platform) | **Minimal & surgical** (one micro-app) |

Exitwise completes the spectrum: as deal size grows, software recedes and humans take over. NextOwner (Acquire-style self-serve) sits at the opposite end — but Exitwise's *funnel machinery* is state of the art and worth studying.

---

## 2. Tech Stack

### 2.1 Verified by direct inspection

| Layer | Technology | Evidence |
|---|---|---|
| Marketing site | **Webflow** (no-code builder) + Webflow CMS | `cdn.prod.website-files.com` assets, `webflow.js` |
| Edge | **Cloudflare** (aggressively bot-filtered — 403 to non-browser agents) | `Server: cloudflare`, CF-RAY |
| Animations | GSAP + SplitType, jQuery 3.5 (Webflow's runtime) | Script tags |
| **Valuation calculator** | A **custom Next.js app (app router)** mounted at `/valuation-calculator` — path-based zone on the same domain | `/valuation-calculator/_next/static/chunks/app/(valuation)/layout-*.js` |
| Exit-readiness quiz | **Tally.so** embedded form (no-code) | `tally.so/embed/nPWk40` iframe script |
| Founders directory search | **Finsweet Attributes** (Webflow CMS filtering library) on `/search-exited-founders` | Finsweet markers in HTML |
| Scheduling | **Calendly** (multiple funnels: `/call`, `/exited-call`, strategy sessions) | Embed signatures |
| Newsletter | **Beehiiv** (embedded subscribe forms + `newsletter.exitwise.com`) | Embed script |
| Podcast | Dedicated `podcast.exitwise.com` site ("Exitwise Productions") | Subdomain |
| Analytics | GTM + **Microsoft Clarity** (session recordings) | Inline snippets |

### 2.2 Inferred

- **No logged-in product.** `app.exitwise.com` doesn't respond; no login link exists anywhere. Deal execution runs on human advisors' own tooling (email, data rooms, bankers' systems) **(inferred)** — consistent with a services business.
- The Next.js calculator presumably posts leads to a CRM (HubSpot-class) **(inferred)**; the calculator is the only place they spent real engineering.

### 2.3 Architecture sketch

```
                exitwise.com  (Cloudflare, one domain)
      ┌──────────────────┬──────────────────────────┬────────────────┐
      ▼                  ▼                          ▼                ▼
  Webflow site       /valuation-calculator      Embedded tools   Subdomains
  (no-code)          CUSTOM NEXT.JS APP         Tally quiz       newsletter. (Beehiiv)
  · homepage/blog    (the one piece of real     Calendly booking podcast.
  · founders dir     engineering — path-zone    Beehiiv forms
    w/ Finsweet       on the same domain)
    search
      │
      └── GTM + MS Clarity ── every page feeds the funnel:
          SEO post → calculator/quiz → Calendly call → human advisory service
```

---

## 3. The Funnel (their real "product")

1. **Long-tail SEO content factory** — hundreds of high-intent posts targeting exact valuation queries: "dental practice valuation," "how much is a car dealership worth," "attorney fees for selling a business." Each ranks for someone *about to sell*.
2. **Interactive lead magnets** — the valuation calculator (custom-built, because it's the #1 magnet) and the exit-readiness quiz (Tally, because a form is enough).
3. **Social proof layer** — the **Exited Founders directory**: ~70 individual founder profile pages, searchable/filterable, each a story of a successful exit. Simultaneously: trust content, SEO pages, and the advisory network's public face.
4. **Conversion** — Calendly strategy-session bookings, with *separate* funnels for founders (`/call`) and exited founders joining the network (`/exited-call`).
5. **Retention channels** — Beehiiv newsletter + podcast for the years-long "not ready to sell yet" audience.

Note how the entire company runs on ~zero custom infrastructure except the one tool where quality matters most.

---

## 4. Cool Features Log (Exitwise)

*(Also recorded in [`cool_features.md`](./cool_features.md).)*

1. **Exited Founders directory** — a searchable gallery of real people who exited, each with a profile page. Social proof + SEO + recruiting for their mentor network, all in one Webflow CMS collection.
2. **Surgical engineering** — no-code everywhere *except* the valuation calculator, which is a real Next.js app path-mounted at `/valuation-calculator`. Independent validation of the path-zone layout NextOwner adopted from Baton — and a masterclass in spending engineering only where it differentiates.
3. **Exit-readiness quiz** — a five-minute Tally form that qualifies and segments leads before any human call. Costs nothing to build; tells sellers "you're not ready yet — here's what to fix" (which itself creates a nurture relationship).
4. **Intent-based SEO factory** — content mapped to *valuation* queries (the moment of highest seller intent), not generic "how to sell" advice.
5. **Dual conversion funnels** — distinct booking flows for customers vs. network advisors; the supply side gets its own funnel.

---

## 5. Functional Notes

- Cloudflare's bot filtering (403 to non-browser agents) is the most aggressive of the three sites studied — worth remembering when NextOwner's own scraping-protection conversation comes up someday.
- Everything measurable: GTM everywhere plus Microsoft Clarity session replays on a marketing site — they watch how visitors use the funnel, not just count them.

---

## 6. Relevance Verdict for NextOwner

### Adopt (as post-MVP marketing playbook, not engineering)
| Idea | Where it fits |
|---|---|
| **Valuation calculator as the flagship lead magnet** | Already Milestone 11 — Exitwise (and Baton, and Acquire) all confirm it's the industry's proven magnet. Their twist worth copying: surround it with intent-based SEO content so it gets found. |
| **"Sold on NextOwner" success-story directory** | The Exited Founders directory, adapted: every closed deal becomes a (seller-approved) story page — social proof + SEO compounding with each close. Post-MVP; needs closed deals first. |
| **Seller-readiness quiz** | A zero-engineering qualification funnel ("Is your business ready to list?") that educates unready sellers and captures them for later — pairs naturally with the M2 listing builder's requirements. A Tally-style embed is genuinely enough. |
| **Owned-audience channels** | Newsletter for the "not ready yet" audience — the years-long nurture Exitwise runs on Beehiiv. Cheap, compounding. |

### Reinforces existing decisions
- **Path-based zones**: their custom calculator mounted at a path on a no-code domain is exactly the §3.4 single-origin pattern — second independent validation.
- **Marketing site ≠ app**: Webflow/no-code marketing decoupled from product engineering echoes the constitution's separation (static `marketing/` folder now, CMS-class tooling later).

### Explicitly do NOT copy
- **The no-app model** — Exitwise has no logged-in product because their product is people. NextOwner's product is software; there's nothing architectural to borrow from their (absent) backend.
- **jQuery/Webflow for anything interactive in the product** — their stack choice is right *for a funnel*, wrong for a marketplace.

---

## 7. Sources

- [exitwise.com](https://exitwise.com/) — homepage, sitemap, `/valuation-calculator`, `/search-exited-founders`, `/exit-readiness-quiz` (HTML/bundle inspection)
- [About Exitwise](https://exitwise.com/about) · [Expert M&A Advisory](https://exitwise.com/m-a-advisory)
- [Todd Sullivan — LinkedIn](https://www.linkedin.com/in/toddfsullivan/)
- [Exitwise Productions podcast](https://podcast.exitwise.com/)
- [The Grafter × Exitwise partnership announcement](https://exitwise.com/blog/the-grafter-exitwise-partnership)
