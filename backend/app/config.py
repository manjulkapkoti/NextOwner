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

    # Test-only: mount the /_debug/boom route (500-contract tests). Off in prod.
    enable_debug_routes: bool = False


# Allowed document types — content-type → extension. Whitelist, not blacklist.
ALLOWED_UPLOAD_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


settings = Settings()
