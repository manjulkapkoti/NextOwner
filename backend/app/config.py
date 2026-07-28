"""Application settings — env-only configuration (constitution: secrets in env).

`pydantic-settings` reads the environment (and an optional `.env`, gitignored) at
import time. The JWT signing key and DB URL live here, never hardcoded in code
(`security.md` §Secrets). `.env.example` ships with placeholders.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (SQLite now → Postgres later via connection-string swap; Article 1)
    database_url: str = "sqlite:///nextowner.db"

    # Auth / JWT
    jwt_secret: str = "dev-only-change-me"          # MUST be overridden in any real env
    jwt_algorithm: str = "HS256"                     # pinned — verifier rejects everything else
    access_token_expire_minutes: int = 60           # short-lived; refresh deferred (security.md §9)
    tos_version: str = "2026-07-17"                  # which ToS text a registration accepted

    # Which platform-NDA text a signature accepted (M5, spec 005 D4). Server-owned
    # so the client can never influence what it is recorded as having signed;
    # frozen onto the user at signature and never re-stamped, because the first
    # signature is the retained legal record.
    nda_version: str = "2026-07-20"

    # Auth-endpoint rate limiting (brute-force / credential stuffing / signup
    # spam — security.md §1.1 requires BOTH login and register).
    login_rate_limit_max: int = 5
    login_rate_limit_window_seconds: int = 60
    register_rate_limit_max: int = 10
    register_rate_limit_window_seconds: int = 60

    # Uploads (M2 — treat as hostile: security.md §2)
    upload_dir: str = "uploads"
    max_upload_bytes: int = 10 * 1024 * 1024          # 10 MB — the per-file ceiling
    # Coarse outer cap on ANY request body, enforced from Content-Length before
    # the body is parsed — stops a multi-GB upload from ever being spooled to
    # disk (security.md §1.1 "cap request body size"). Sits above the per-file
    # ceiling to allow multipart overhead.
    max_request_bytes: int = 12 * 1024 * 1024         # 12 MB

    # Per-owner upload quota (M10, spec 010 D8/D11 — the `milestones.md` M10
    # fold-in, "a per-listing upload count / total-size quota"). "Owner" is the
    # owning *entity*: a listing for `ListingDocument`, a user for
    # `BuyerVerificationDocument`. `max_upload_bytes` above bounds one file; these
    # bound the set, which a 20-file owner could otherwise multiply.
    #
    # Deliberately generous (D11): a DoS control, not a workflow limit. A review
    # cycle needs one document, so a caller reaching 20 is churning the queue —
    # which is precisely what the fold-in asked us to bound. The cost of the
    # generosity is recorded, not hidden: at the cap a rejected buyer's
    # resubmission *is* refused, and the way out is an admin, not a retry.
    max_documents_per_owner: int = 20
    max_total_upload_bytes_per_owner: int = 50 * 1024 * 1024      # 50 MB

    # The admin-authored buyer-verification rejection reason (M10, spec 010 X6).
    # Free text that is stored *and echoed back to the buyer* via
    # `GET /api/verification`, so it is bounded at the boundary like the two
    # `offer_*_max_chars` fields above (`security.md` §1.1).
    verification_reason_max_chars: int = 1000

    # Chat (M6, spec 006). The size cap is a WS boundary rule (D2), not a
    # column constraint; the rate cap is per-connection, mirroring the auth
    # limiters' shape (`security.md` §6 DoS surface).
    chat_message_max_chars: int = 4000
    chat_rate_limit_max: int = 20
    chat_rate_limit_window_seconds: int = 10
    chat_history_page_limit: int = 50

    # Offers / LOI (M7, spec 007 D6). Bound the two free-text terms fields at
    # the boundary (security.md §2) — a floor of "some text" isn't needed since
    # both are optional-length beyond structure's minimum, but an unbounded
    # ceiling on user-entered deal terms is a DoS/storage surface like any other.
    offer_structure_max_chars: int = 200
    offer_contingencies_max_chars: int = 2000

    # Email channel (M8, spec 008 D9). MailHog locally: SMTP on 1025, inbox UI
    # on 8025 — a real inbox with no external service (Article 1, 100% local).
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "no-reply@nextowner.local"
    email_enabled: bool = True
    # Where links in outbound mail point. Server-owned so a client can never
    # influence the host in a reset link (that would be a phishing primitive).
    app_base_url: str = "http://localhost:5173"

    # Account-lifecycle tokens (M8, security.md §7 M8). Short expiry is half the
    # defense; single-use + hashed-at-rest is the other half (spec 008 D5).
    password_reset_token_ttl_minutes: int = 30
    email_verification_token_ttl_hours: int = 24
    # Requesting a reset mails a third party on demand — bound it harder than
    # login, because the cost of abuse lands on someone who did nothing.
    forgot_password_rate_limit_max: int = 3
    forgot_password_rate_limit_window_seconds: int = 900

    # Notifications & saved searches (M8). The per-user search cap bounds the
    # fan-out cost of a single publication (spec A9, NFR Scalability); the page
    # limit is the same DoS control M4's browse already applies.
    saved_search_max_per_user: int = 20
    notifications_page_limit: int = 50

    # Rate limits for the surfaces four milestones each deferred (pre-011, D5).
    # Per-surface rather than one global number: browse is something a real user
    # does constantly, a password reset is something they do twice a year.
    #
    # Per IP per minute. A real visitor paging and filtering fires a handful a
    # minute; 120 is well clear of human use and still bounds a scraper.
    browse_rate_limit_max: int = 120
    browse_rate_limit_window_seconds: int = 60
    # Per **user** per hour. A genuine buyer asks for access to a few listings in
    # a sitting; 10/hour makes the fan-out attack (security.md §9, M5) slow
    # enough to be pointless.
    access_request_rate_limit_max: int = 10
    access_request_rate_limit_window_seconds: int = 3600
    # Per **user** per hour, shared by both document routes. Complements the
    # *stored* quota above (20 files / 50 MB) with a bound on arrival *rate* —
    # which is what actually narrows the read-then-insert race D11 accepted.
    upload_rate_limit_max: int = 20
    upload_rate_limit_window_seconds: int = 3600
    # Per **email address** per hour — the victim-side cap (D6), alongside the
    # per-IP `forgot_password_rate_limit_*` above. They defend different victims:
    # per-IP stops one attacker burning our mail budget, per-address stops N
    # attackers burying one person's inbox.
    forgot_password_address_rate_limit_max: int = 3
    forgot_password_address_rate_limit_window_seconds: int = 3600

    # **The security-relevant one** (pre-011 D3). The addresses of proxies we
    # actually run. Empty (the default) means the immediate peer is never
    # trusted, so `X-Forwarded-For` is ignored entirely — correct locally and
    # safe everywhere, because a client can send that header itself and a limiter
    # keyed on it unconditionally is *weaker* than no limiter (the caller picks a
    # fresh counter per request). A deployment lists its own reverse proxy / CDN
    # egress addresses here. Set from the environment as JSON, e.g.
    # `TRUSTED_PROXIES='["10.0.0.1"]'`.
    #
    # Replaced a `trusted_proxy_count` integer (D3's amendment): a count could
    # not express a single-nginx chain, and its safety depended on the operator
    # matching hop depth exactly — set too high, the index landed inside
    # attacker-supplied text. A wrong entry here can only merge callers into one
    # bucket, which is the safe direction.
    trusted_proxies: list[str] = []

    # Test-only: mount the /_debug/boom route (500-contract tests). Off in prod.
    enable_debug_routes: bool = False


# Allowed document types — content-type → extension. Whitelist, not blacklist.
ALLOWED_UPLOAD_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


settings = Settings()
