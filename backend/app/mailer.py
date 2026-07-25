"""Outbound email — behind a swappable port (spec 008 D9).

Named ``mailer.py`` and **not** ``email.py`` on purpose: a module called
``email`` inside this package is a trap for anyone reading imports, because
``smtplib`` itself imports the stdlib ``email`` package.

Same shape as ``ratelimit.py``'s ``RateLimiterBackend`` and
``chat_broker.py``'s ``ChatBroker`` — this codebase's established way of
keeping an external or per-instance effect swappable. The SMTP implementation
talks to **MailHog** locally (SMTP on ``localhost:1025``, a real inbox UI on
``:8025``), so the whole milestone is exercisable with zero external service,
per Article 1's "100% local".

Two properties this module is responsible for, both load-bearing:

1. **A send failure never propagates.** `send_safe` swallows and logs. An SMTP
   outage must not turn an access approval into a 500 (F4), and — more
   sharply — must not turn `forgot-password` into the enumeration oracle its
   uniform 202 exists to prevent (X3).
2. **Nothing secret is ever logged.** The failure log records the recipient and
   the subject, never the body: reset and verification links live in bodies
   (`security.md` §7 M8 — "never put the token in a log").
"""

from __future__ import annotations

import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from typing import Protocol

from sqlalchemy import event
from sqlalchemy.orm import Session as SASession

from .config import settings

logger = logging.getLogger("nextowner.mailer")


class EmailSender(Protocol):
    """The seam. A queue- or vendor-backed sender implements this one method."""

    def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpEmailSender:
    """Plain SMTP to MailHog. No auth and no TLS — correct for a local sink,
    and the reason `settings.email_enabled` exists to switch it off entirely."""

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.send_message(message)


class NullEmailSender:
    """Drops everything. The `email_enabled=False` implementation."""

    def send(self, to: str, subject: str, body: str) -> None:
        return None


def send_safe(to: str, subject: str, body: str) -> bool:
    """Send, swallowing any transport failure. Returns whether it went out.

    Every caller in the app uses this rather than `mailer.send` directly, so
    the "email never fails the business action" rule is one function rather
    than a `try` block each call site could forget (F4, X3).
    """
    try:
        mailer.send(to, subject, body)
    except Exception:
        # Recipient + subject only — never the body, which carries the token.
        logger.warning("email dispatch failed [to=%s subject=%s]", to, subject)
        return False
    return True


# ── send-after-commit ────────────────────────────────────────────────────────
#
# Email is the one effect in this codebase that a database rollback cannot take
# back. Sending inline would mean a buyer can be told their offer was accepted
# by a transaction that then failed its unique constraint and rolled away —
# `create_offer` and `counter_offer` both have exactly that path
# (`IntegrityError` → `session.rollback()`).
#
# So callers **queue** onto the session and the queue drains in SQLAlchemy's
# `after_commit`, which by definition only fires when the work actually landed.
# `after_soft_rollback` throws the queue away. The result is that a mail is
# sent if and only if the fact it describes is durable.

_PENDING = "nextowner_pending_emails"


class Dispatcher(Protocol):
    """Where a queued send actually runs. The second seam in this module."""

    def submit(self, fn: object, *args: object) -> None: ...


class InlineDispatcher:
    """Runs the send on the calling thread. Used by tests, so assertions are
    deterministic — and never in production, for the reason below."""

    def submit(self, fn, *args) -> None:  # type: ignore[no-untyped-def]
        fn(*args)


class ThreadDispatcher:
    """Runs sends on a small worker pool — **the production default.**

    `SmtpEmailSender.send` is a blocking socket call with a 5-second timeout,
    and the drain below is triggered by `session.commit()`. Left inline, that
    put a blocking network call on whatever thread committed, including the
    **`async` WebSocket handler** in `routers/chat.py`: one slow SMTP server
    would stall every live chat socket on that worker for up to five seconds,
    against an NFR of sub-second message delivery.

    It also removed a timing side-channel from `forgot-password`: with the send
    inline, the known-address path paid an SMTP round trip that the
    unknown-address path did not, so response latency answered the question the
    uniform 202 exists to refuse (`security.md` §6 — enumeration by timing, the
    rule M1's login already honours with its dummy-hash).

    Per-instance state, like `ratelimit.py` and `chat_broker.py` before it: a
    real queue replaces this by constructing a different dispatcher, not by
    editing any caller.
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mail")

    def submit(self, fn, *args) -> None:  # type: ignore[no-untyped-def]
        self._pool.submit(fn, *args)


def queue_email(session: SASession, to: str, subject: str, body: str) -> None:
    """Hold a message until this session's transaction commits."""
    session.info.setdefault(_PENDING, []).append((to, subject, body))


@event.listens_for(SASession, "after_commit")
def _flush_pending_emails(session: SASession) -> None:
    for to, subject, body in session.info.pop(_PENDING, []):
        dispatcher.submit(send_safe, to, subject, body)


@event.listens_for(SASession, "after_soft_rollback")
def _drop_pending_emails(session: SASession, previous_transaction: object) -> None:
    session.info.pop(_PENDING, None)


mailer: EmailSender = SmtpEmailSender() if settings.email_enabled else NullEmailSender()
dispatcher: Dispatcher = ThreadDispatcher()
