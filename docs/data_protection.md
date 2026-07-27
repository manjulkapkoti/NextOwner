# Data Protection & Privacy — the technical slice

> The **engineering** slice of data protection: what's cheap to bake into the
> data model now and expensive to retrofit later. Binding alongside the
> constitution for these technical decisions.
>
> **Deliberately out of scope here (owned by the future `legal-compliance` role,
> triggered by real users / a live vendor):** the GDPR/CCPA data-subject request
> *flows*, consent + cookie-consent (TCF) tooling, DPAs / vendor agreements,
> breach-notification process, retention *policy* (durations), and at-rest
> encryption (arrives with the Postgres swap). Building that machinery for a
> 100%-local MVP with mocked vendors and zero real users would be premature.
> The requirement itself is already captured — `requirements.md` §3 NFR *Privacy
> & compliance*.

---

## 0. Two halves of "data protection"

- **Confidentiality / access-control** — keeping sensitive data from unauthorized users. This is the **product core** (NDA gate, public/private split, `require_private_access`, response-model leak prevention, audit rows). See `docs/security.md`.
- **Regulatory privacy / data lifecycle** — this doc's technical slice (below) + `legal-compliance` for the policy layer.

## 1. PII inventory (know where personal data lives)

| Data element | Where | Control |
|---|---|---|
| Email | `user` | identifier; never on public `response_model`s; never logged |
| Password | `user` (bcrypt **hash** only) | never plaintext, never logged, never returned |
| Business financials (private) | `listing_private` | NDA-gated (`require_private_access`) |
| Chat messages | `conversation` / `message` | membership-gated |
| Offers / prices | `offer` | approved-access gated |
| NDA acceptance | `user.nda_signed_at` + audit rows | retained with timestamp (legal record) |
| KYC / identity docs | **not stored by us** — the vendor holds them (§4) | store only the *result* |
| IP / analytics events | `track()` (console for now) | never carries private/identity fields |

## 2. Data minimization

- **Collect / store / expose only what's needed.** Don't add a PII column without a reason; don't return it in a public schema; don't log it.
- Public `response_model`s exclude identity fields **by schema** (already enforced; covered by the schema-leak test).

## 3. Erasure & anonymization — design the schema erasure-ready **from M1**

The one thing that's painful to retrofit. A user is referenced by listings, messages, offers, access-requests, uploads — so **hard-delete breaks history + audit**. The pattern:

- **Anonymize-in-place over hard-delete** for referenced people. On erasure: null/replace PII fields (email → a tombstone like `deleted-user-{id}@nextowner.invalid`), set a `deleted_at` / `is_deleted` flag, and **keep the FK rows** for referential integrity + audit.
- **Ship the `user` table erasure-ready at M1** — include the soft-delete / anonymization path in the schema even though the user-facing erasure endpoint (a GDPR flow) comes later with `legal-compliance`. The *schema* must support it from the start.
- **Decide per child table** whether erasure **cascades** (delete) or **anonymizes** (keep the row, drop the person): e.g. offers/access-requests → keep for audit with the author anonymized; uploaded files → delete from `uploads/`.
- **Audit rows are immutable and exempt** — they reference **ids + minimal data, not PII snapshots**, so anonymizing a user never breaks the audit trail. (This is *why* audit rows must not copy PII in.)

## 4. KYC / identity documents — held by the vendor, not us

Follow the Acquire pattern (`research/acquire_design.md`): the verification vendor (Persona) **holds the identity documents**; our DB stores **only the verification result** (`verified: bool`, timestamp, a vendor reference) — never the raw docs. This minimizes our most sensitive PII surface.

> **⚠ M10 ships a recorded deviation from the sentence that used to close this paragraph** (*"The M10 mock must model this: our DB never receives the document, only the outcome"*). It does not, and could not: F11 and `design_implementation.md` Part 4 both specify **manual** review by our own admin, which is impossible unless a system of ours holds the file — there is no vendor to hand it to yet. So `BuyerVerificationDocument` stores the document, readable by the uploader and by an admin and nobody else. **The goal of this section is honoured as far as MVP allows** — the file is served only through a permission-checked route (never statically), its contents are never parsed, and the *profile-facing* surfaces carry only `verification_status` + a timestamp, never the file. The paragraph above remains the target state: when a real KYC vendor is integrated, the upload route is replaced by their widget plus a webhook, and this deviation retires with the code that caused it. Full reasoning: **spec 010 D9**; erasure consequences: **D10** (hard-delete row + file, and never by directory — the key space is shared with listing documents).

## 5. Retention (pointers; durations → `legal-compliance`)

- NDA acceptance + audit log → **retained** (legal records / immutable).
- Data-room + uploaded docs → retained while the deal is active; deletion on listing removal / access revocation (design the delete path).
- Exact retention **durations** and the legal basis → `legal-compliance`.
- **Data export / portability** (a GDPR/CCPA data-subject flow, like erasure) → the flow itself is `legal-compliance`'s; the API-only-door design makes a per-user export endpoint a straightforward later add.

## 6. In the SDD loop (per milestone)

- Any milestone that **adds a PII field** or a **table referencing a person** records it in the plan's **Data protection** item: what PII, and its erasure/anonymization behavior.
- The `user` table (M1) ships **erasure-ready**.
- Public `response_model`s exclude identity (schema-leak test).

## 7. Checklist (per milestone touching data)

- [ ] New PII fields are justified (data-min), excluded from public `response_model`s, and never logged.
- [ ] New person-referencing tables have a defined **erasure/anonymization** behavior (cascade vs anonymize).
- [ ] The `user` table is **erasure-ready** (soft-delete / anonymize path) from M1.
- [ ] KYC / identity docs are held by the vendor, not our DB (only the result is stored). **Not met at MVP, deliberately — see the M10 deviation note in §4.** Re-check this box when a real KYC vendor replaces the manual mock; until then the compensating controls are the permission-gated download route, admin-or-uploader-only access, and no parsing of contents.
- [ ] Audit rows store ids + minimal data (no PII snapshots), so anonymization can't break them.
