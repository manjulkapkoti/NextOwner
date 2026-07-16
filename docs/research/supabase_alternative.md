# Alternative Approach: Supabase (BaaS) Instead of a Custom Backend

> **Status: considered and rejected — kept as reference.** Constitution Article 1 records the decision: *"Supabase (BaaS, no custom backend) — fastest path, but less is learned and backend logic wouldn't be Python."* **NextOwner's stack is the FastAPI backend of [`../design_implementation.md`](../design_implementation.md) Parts 3–4, and Milestone 0 has shipped on it.** Nothing here is binding; do not mix the two approaches.
>
> **Why keep it:** it shows how the same MVP looks with *no custom backend at all* — the philosophy Acquire itself follows (with Firebase). It's the clearest way to see what the FastAPI choice buys and costs. The Firebase comparisons below refer to Acquire's real stack, described in [`acquire_design.md`](./acquire_design.md) §4.
>
> *Moved here 2026-07-16 from `design_implementation.md` Part 6, so the implementation guide contains only NextOwner's design. Content unchanged; sections renumbered 6.x → 1–7.*

---

## 1. What Supabase is

Supabase is an open-source "Firebase alternative" built around **PostgreSQL** — a classic relational (SQL) database — with the same convenience layers Firebase offers: hosted Auth, auto-generated APIs, realtime subscriptions, file storage, and serverless functions. The philosophical difference:

|                   | Firebase                                       | Supabase                                                                     |
| ----------------- | ---------------------------------------------- | ---------------------------------------------------------------------------- |
| Database          | Firestore — NoSQL documents, schemaless        | **Postgres — tables, columns, foreign keys, SQL**                            |
| Access control    | Security-rules language (proprietary)          | **Row Level Security (RLS)** — standard Postgres policies written in SQL     |
| Server logic      | Cloud Functions (Node)                         | **Postgres functions/triggers (SQL)** + **Edge Functions (Deno/TypeScript)** |
| Realtime          | Firestore listeners (per-query, very granular) | Realtime channels streaming table changes (per-table/filter)                 |
| Local development | Emulator Suite (Java-based)                    | **`supabase start` — the entire stack in Docker**                            |
| Openness          | Proprietary Google service                     | Open source; the local stack IS the production stack                         |

**Local story:** install **Docker Desktop**, then `supabase start` boots the whole platform on your machine — Postgres, Auth, Storage, Realtime, Edge Functions, plus **Supabase Studio** (a web dashboard) at `localhost:54323`. Completely free, no account needed. Docker is the one prerequisite.

```bash
npm install -g supabase        # or: winget install Supabase.cli
supabase init                  # creates supabase/ folder in your project
supabase start                 # boots Postgres + Auth + Storage + Studio in Docker
cd app && npm i @supabase/supabase-js
```

```ts
// app/src/lib/supabase.ts — replaces lib/api.ts
import { createClient } from "@supabase/supabase-js";
export const supabase = createClient(
  "http://localhost:54321", // local API gateway
  "<anon key printed by `supabase start`>",
);
```

## 2. Component-by-component mapping

Every box in the architecture diagram survives — only its implementation changes:

| Diagram component                                             | Firebase (Acquire's real stack) | Supabase implementation                                                                                                                                                                                 |
| ------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Web App (React/Vite/MUI/MobX)                                 | unchanged                       | **unchanged** — only the data-access code in stores changes                                                                                                                                             |
| Firebase Auth                                                 | Firebase Auth, JWT              | **Supabase Auth** (email, Google OAuth) — also issues a JWT; same mental model                                                                                                                          |
| Firestore (listings, deals, chat)                             | Document collections            | **Postgres tables** with foreign keys (schema in §3)                                                                                                                                                   |
| Security rules / NDA gate                                     | `firestore.rules`               | **RLS policies** in SQL (example in §4)                                                                                                                                                                |
| Cloud Functions — callables (`submitOffer`, `approveListing`) | `httpsCallable`                 | Two options: **Postgres functions** called via `supabase.rpc("submit_offer", {...})` (best for pure data logic — transactional!) or **Edge Functions** (TypeScript) when you need to call external APIs |
| Cloud Functions — triggers (`onListingPublished`)             | Firestore trigger               | **Postgres trigger** on `UPDATE listings` (SQL, instant) or a **database webhook → Edge Function**                                                                                                      |
| Cloud Storage (data room)                                     | Storage buckets + rules         | **Supabase Storage** — buckets with their own RLS-style policies                                                                                                                                        |
| Realtime Database (presence)                                  | RTDB                            | skipped (Supabase Realtime has built-in **Presence** if you ever want online-dots)                                                                                                                      |
| Realtime chat updates                                         | `onSnapshot` listener           | `supabase.channel(...).on("postgres_changes", ...)` subscription (example in §5)                                                                                                                       |
| App Check                                                     | App Check                       | skipped locally (production: captcha protection on Auth)                                                                                                                                                |
| Stripe / Persona / Escrow / ChartMogul mocks                  | mock functions + state fields   | **identical approach** — same state machines, same fixtures                                                                                                                                             |
| Data inspection                                               | Firebase console / Emulator UI  | **Supabase Studio** at localhost:54323 (+ full SQL editor)                                                                                                                                              |
| Observability                                                 | console.log `track()`           | **unchanged**                                                                                                                                                                                           |

## 3. The data model as a SQL schema

This is the same relational schema your FastAPI build uses (§3.5 shows it as SQLModel classes) — written out here as raw SQL migrations. Relational modeling is where a _marketplace_ genuinely benefits: filters, sorting, joins, and aggregations ("avg multiple by category") are one SQL query.

```sql
-- supabase/migrations/0001_schema.sql  (versioned migrations: a big win)

create table profiles (
  id uuid primary key references auth.users(id),   -- 1:1 with the auth user
  role text check (role in ('buyer','seller','both')),
  display_name text,
  buyer_verified boolean default false,
  nda_signed_at timestamptz,                       -- platform NDA, signed once
  is_admin boolean default false,
  created_at timestamptz default now()
);

create table listings (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid references profiles(id) not null,
  status text default 'draft'
    check (status in ('draft','pending_review','live','under_offer','sold','rejected','paused')),
  type text, headline text, description text,
  asking_price numeric, ttm_revenue numeric, ttm_profit numeric,
  mrr numeric, churn_pct numeric, customers int,
  tech_stack text[], reason_for_sale text,
  created_at timestamptz default now(), published_at timestamptz
);

create table listing_private (                      -- the data room (NDA-gated)
  listing_id uuid primary key references listings(id),
  company_name text, website_url text,
  detailed_financials jsonb, document_paths text[]
);

create table access_requests (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid references listings(id) not null,
  buyer_id uuid references profiles(id) not null,
  status text default 'requested' check (status in ('requested','approved','denied')),
  requested_at timestamptz default now(), decided_at timestamptz,
  unique (listing_id, buyer_id)
);

create table conversations (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid references listings(id),
  buyer_id uuid references profiles(id),
  seller_id uuid references profiles(id),
  last_message_at timestamptz
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references conversations(id) not null,
  sender_id uuid references profiles(id) not null,
  text text not null, sent_at timestamptz default now()
);

create table offers (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid references listings(id) not null,
  buyer_id uuid references profiles(id) not null,
  price numeric, structure text, conditions text, close_by date,
  status text default 'submitted'
    check (status in ('submitted','accepted','declined','countered','withdrawn')),
  created_at timestamptz default now()
);

create table offer_events (                          -- audit trail as rows, not array
  id bigint generated always as identity primary key,
  offer_id uuid references offers(id), action text,
  actor_id uuid, price numeric, at timestamptz default now()
);

create table saved_searches (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id), filters jsonb, created_at timestamptz default now()
);

create table watchlist (
  user_id uuid references profiles(id),
  listing_id uuid references listings(id),
  primary key (user_id, listing_id)
);
```

Notes on the relational idiom (these apply to your FastAPI schema too):

- **Foreign keys** replace "store the id and hope" — the DB _guarantees_ an offer points at a real listing.
- The offer **audit trail is its own table** (`offer_events`) instead of an array inside a document.
- **`unique (listing_id, buyer_id)`** enforces one NDA per buyer per listing at the database level.
- Migrations live in `supabase/migrations/*.sql`, versioned in git — rebuild the whole schema anywhere with `supabase db reset`.

## 4. The NDA gate as Row Level Security

RLS is the declarative equivalent of the FastAPI `require_private_access` dependency (§3.6): policies attached to tables that filter every query automatically, no matter what the client asks for — necessary here because with a BaaS the browser talks to the database directly. The listing rules and the NDA gate as policies:

```sql
alter table listings enable row level security;
alter table listing_private enable row level security;

-- Public may see live listings; owners see their own in any status
create policy "public reads live listings" on listings
  for select using (status = 'live' or owner_id = auth.uid());

-- Sellers may create their own drafts (but cannot self-publish: no UPDATE-to-live policy)
create policy "sellers create drafts" on listings
  for insert with check (owner_id = auth.uid() and status = 'draft');

-- THE NDA GATE: private data readable only by the owner or an approved requester
create policy "nda gate" on listing_private
  for select using (
    exists (select 1 from listings l
            where l.id = listing_id and l.owner_id = auth.uid())
    or exists (select 1 from access_requests ar
               where ar.listing_id = listing_id
                 and ar.buyer_id = auth.uid()
                 and ar.status = 'approved')
  );
```

`auth.uid()` is the logged-in user's id extracted from the JWT — the same concept as `get_current_user` in FastAPI. Test policies in Studio's SQL editor by impersonating roles.

Privileged transitions (`approveListing`, `submitOffer`) become **Postgres functions** with `security definer` (they run with elevated rights, bypassing RLS — the counterpart of admin-only FastAPI endpoints):

```sql
create function approve_listing(p_listing_id uuid) returns void
language plpgsql security definer as $$
begin
  if not exists (select 1 from profiles where id = auth.uid() and is_admin) then
    raise exception 'not authorized';
  end if;
  update listings set status = 'live', published_at = now()
  where id = p_listing_id and status = 'pending_review';
end $$;
```

Called from React with one line: `await supabase.rpc("approve_listing", { p_listing_id: id })` — and it's **transactional by default**.

## 5. Realtime chat, the Supabase way

```ts
// the chat subscription — counterpart of the FastAPI WebSocket (Milestone 6)
const channel = supabase
  .channel(`conv-${conversationId}`)
  .on(
    "postgres_changes",
    {
      event: "INSERT",
      schema: "public",
      table: "messages",
      filter: `conversation_id=eq.${conversationId}`,
    },
    (payload) => chatStore.addMessage(payload.new),
  )
  .subscribe();
```

Same user experience (two browser windows updating live), no server code to write: you subscribe to _table changes matching a filter_. One practical difference: new subscribers don't get history pushed automatically — `select` past messages first, then subscribe for inserts. RLS still applies to what the stream delivers.

## 6. What changes per milestone (relative to the FastAPI plan in [`../design_implementation.md`](../design_implementation.md) Part 4)

| Milestone              | Change when using Supabase                                                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 0 — Hello              | `supabase start` instead of `fastapi dev` + SQLite; insert a row via Studio, read it from React                                            |
| 1 — Auth & roles       | Supabase Auth replaces your JWT endpoints; `profiles` row created by a Postgres trigger on `auth.users` insert (standard pattern)          |
| 2 — Listing builder    | Form writes rows directly via `supabase-js` (RLS permitting) instead of calling your API; uploads to a Storage bucket                      |
| 3 — Curation           | `approve_listing` / `reject_listing` as `security definer` SQL functions (§4) instead of admin endpoints                                  |
| 4 — Marketplace browse | Filters via `supabase.from("listings").select().gte().lte().order().range()` — no API layer to write                                       |
| 5 — NDA gate           | RLS policy (§4) instead of the `require_private_access` dependency — same logic, enforced by the DB                                       |
| 6 — Chat               | Realtime channel subscription (§5) instead of hand-built WebSockets                                                                       |
| 7 — Offers             | `submit_offer` / `respond_to_offer` SQL functions; audit rows in `offer_events`; transactional accept                                      |
| 8 — Alerts             | Postgres trigger on `listings` update → inserts `notifications` rows (realtime-subscribed inbox); MailHog trick works via an Edge Function |
| 9 — Watchlist          | Trivial insert/delete on the `watchlist` table via `supabase-js`                                                                           |
| 10 — Verification      | Same mock design; file in Storage + `buyer_verified` flag                                                                                  |
| 11 — Valuation calc    | Pure frontend — zero change                                                                                                                |

## 7. Trade-offs — how to choose

**Stay with FastAPI (Parts 3–4 — your current choice) if…**

- You want the backend in **Python** — the same language as the future agentic layer, LLM SDKs, and data tooling.
- You want to _learn by building_ the mechanics (auth, permissions, WebSockets) rather than configuring them.
- You want maximum control and the most transferable skills: REST design, SQL, JWT, API testing.

**Pick Firebase (Acquire's actual stack) if…**

- You want to mirror the real Acquire.com architecture you researched — maximum fidelity to the case study.
- You want realtime to be the default behavior of every query, with zero extra wiring.

**Pick Supabase (this part) if…**

- You want relational + SQL but with **no custom server at all** — the fastest path to a working product.
- You value RLS, versioned migrations, and an open-source stack where local == production.

**What does NOT change in any of the three:** the React/Vite/MUI frontend, the mock strategy for Stripe/Persona/Escrow/ChartMogul, the milestones' order and business meaning, and the core mental model — state machines + access rules + realtime views. That's the sign of a good architecture: the business logic survives a full backend swap.
