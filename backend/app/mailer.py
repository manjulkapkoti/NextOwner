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


def queue_email(session: SASession, to: str, subject: str, body: str) -> None:
    """Hold a message until this session's transaction commits."""
    session.info.setdefault(_PENDING, []).append((to, subject, body))


@event.listens_for(SASession, "after_commit")
def _flush_pending_emails(session: SASession) -> None:
    for to, subject, body in session.info.pop(_PENDING, []):
        send_safe(to, subject, body)


@event.listens_for(SASession, "after_soft_rollback")
def _drop_pending_emails(session: SASession, previous_transaction: object) -> None:
    session.info.pop(_PENDING, None)


mailer: EmailSender = SmtpEmailSender() if settings.email_enabled else NullEmailSender()
