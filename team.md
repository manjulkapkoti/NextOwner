# NextOwner — Agent Team

The specialized Claude Code agents that build and run NextOwner. Defined in `.claude/agents/*.md`; roles mirror `docs/team_strategy.md`.

**Status:** ✅ = created/active (Phase 1) · ⬜ = planned (added when its work first appears — the `tech-lead` and `product-lead` agents recommend these on trigger; see `docs/team_strategy.md` § When to hire).

| Agent | Roles & Responsibilities | Tools | Model | Reports to | Expertise |
|---|---|---|---|---|---|
| ✅ `product-lead` | Owns the roadmap (M0→M11), prioritizes the FR-1…23 backlog & MVP cut, defines the curation policy and monetization model; bridges business ↔ build. Recommends the business/ops/advisory hires. | Full toolset | sonnet | Owner | Marketplace/fintech product sense; turning requirements into scoped, testable milestones; spec-just-in-time. |
| ✅ `tech-lead` | Guardian of the "API is the only door" architecture; code review, SDD enforcement, the SQLite→Postgres migration, agent-readiness invariants. Recommends the engineering hires. | Full toolset | **opus** | Owner | Full-stack — Python/FastAPI, React+TS, SQL *and* NoSQL — with system design as the strongest axis. |
| ✅ `backend-engineer` | FastAPI/SQLModel; `permissions.py` trust boundaries, state machines (listing/offer/access), the NDA gate, WebSocket chat, mocked-vendor interfaces. | Full toolset | **opus** | `tech-lead` | Python/FastAPI + SQL/NoSQL data modeling; API-security patterns (default-deny, no-IDOR); full-stack. |
| ✅ `frontend-engineer` | React/Vite/MUI/MobX SPA — listing wizard, browse with anonymous cards, data-room/chat UI, admin queue, dashboards, the `lib/api.ts` JWT layer. | Full toolset | sonnet | `tech-lead` | React + JavaScript/TypeScript, MUI/MobX; client-side leak prevention & XSS-safe rendering; full-stack. |
| ⭐ ✅ `appsec-engineer` | **#1 priority.** Owns `docs/security.md`; threat-models each milestone, red-teams the NDA gate, drives permission tests, hardens auth/JWT/uploads/secrets, runs the touched→must-cover matrix, can block merges. | Full toolset | **opus** | `tech-lead` (→ Owner on security) | Product/application security across the whole stack; adversarial testing; auth/crypto, upload safety, supply-chain. |
| ✅ `product-designer` | Two-sided flows and trust UX (NDA signing, access requests, data room, verified-buyer badges); MUI design system; conversion surfaces (valuation calculator). | Full toolset | sonnet | `product-lead` | Marketplace/SaaS UX; trust & conversion design; MUI design systems. |
| ⬜ `devops-sre` | Single-origin deploy (reverse proxy for `/api` + `/ws`), CI/CD, the Postgres + Alembic migration, backups, secrets manager, observability. | Full toolset | sonnet | `tech-lead` | DevOps/SRE, CI/CD, PostgreSQL, infra & observability; system design. |
| ⬜ `qa-sdet` | Deepen negative/permission-test coverage, build the Playwright golden-path E2E, add load/perf testing. | Full toolset | sonnet | `tech-lead` | Test automation (pytest, Vitest, Playwright); security/negative testing; Python + TypeScript. |
| ⬜ `ai-ml-engineer` | Post-MVP agentic layer (deal-scout, diligence agent) as scoped users through the same gates; tool-calling/MCP; evals-as-pytest; `agent_runs` tracing; pgvector. | Full toolset | **opus** | `tech-lead` | LLM/agents, tool-calling & MCP, RAG/pgvector, evals; Python. |
| ⬜ `trust-safety-ops` | The curation queue (the quality moat), fraud detection, buyer-verification review, dispute handling. | Read-only (`Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch`) | sonnet | `product-lead` | Marketplace trust & safety, fraud/abuse operations, content review. |
| ⬜ `legal-compliance` | NDA framework, Terms of Service, escrow/APA, KYC/AML, GDPR/CCPA data privacy, trademark. | Read-only | sonnet | `product-lead` | Tech/marketplace legal & compliance; M&A/escrow; data-privacy regimes. |
| ⬜ `growth-marketing` | Liquidity & cold-start, SEO, category landing pages, the valuation-calculator funnel, saved-search/alert re-engagement. | Read-only | sonnet | `product-lead` | Marketplace growth, SEO/content, two-sided liquidity. |
| ⬜ `data-analyst` | Funnel & cohort analysis off `track()` events, listing→offer conversion, retention metrics. | Read-only | sonnet | `product-lead` | Product analytics; funnel/cohort/retention analysis; SQL. |

## Reporting structure

```
Owner (you)
├── product-lead ── product-designer · trust-safety-ops ⬜ · legal-compliance ⬜ · growth-marketing ⬜ · data-analyst ⬜
└── tech-lead ───── backend-engineer · frontend-engineer · appsec-engineer ⭐ · devops-sre ⬜ · qa-sdet ⬜ · ai-ml-engineer ⬜
```

`appsec-engineer` reports to `tech-lead` for delivery but escalates security decisions directly to the Owner — the trust boundary is the product, so it can block a merge regardless of hierarchy.

## Notes

- **"Full toolset"** = the agent inherits all Claude Code tools (it builds/edits code). **"Read-only"** advisory agents get research tools only — they advise and review, they don't edit the codebase.
- **Models** follow the cost/risk strategy: **opus** for security-critical, architecture, and agentic work; **sonnet** for routine build, design, and advisory roles.
- **Adding a ⬜ agent:** it's created the moment its work first appears (agents are free — no runway to protect). The active leads flag the trigger live; full reasoning in `docs/team_strategy.md` § When to hire.
