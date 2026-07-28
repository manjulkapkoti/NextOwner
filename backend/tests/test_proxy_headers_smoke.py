"""spec pre-011 S9 — the one test that runs the REAL server stack.

Every other test in this suite uses `TestClient`, which speaks ASGI directly to
the `FastAPI` app object. Uvicorn's `ProxyHeadersMiddleware` is applied *outside*
that object, by uvicorn's own bootstrap — so `TestClient` never runs it, and the
single most dangerous failure mode this branch has is therefore invisible to all
16 other criteria:

    Uvicorn enables ProxyHeadersMiddleware by default (trusted_hosts="127.0.0.1")
    and OVERWRITES scope["client"] from X-Forwarded-For before our first line of
    code runs. `client_ip` then sees an attacker-chosen peer, finds it absent from
    an empty `trusted_proxies`, and keys on it — so every per-IP limit is evaded
    by varying one header.

There is no in-application defence: the real peer is gone before we are called.
The mitigation is the launch command (`--no-proxy-headers`), documented in
`security.md` §9 and `design_implementation.md` §3.4 — and, until this file,
guaranteed by nothing but that documentation. A control whose only protection is
a line in a doc is a control waiting to be switched off.

**Why this test asserts the vulnerable behaviour too.** It boots twice: once with
the flag (the limit must hold) and once without (the limit must be evadable). The
second assertion looks strange until you ask what the first one alone would
prove: if a bug made the browse limiter refuse everything, or if the forged header
never reached the app at all, the with-flag half would pass while testing nothing.
The pair is what makes this sensitive *to the flag* rather than to the weather.
The without-flag half is a statement about uvicorn's documented behaviour, not an
endorsement of it.

Kept in its own file because its mechanics (subprocess, sockets, polling) have
nothing in common with the rest of the suite, and because it is the only test
here that costs seconds rather than milliseconds.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Two requests allowed, so the third answers the question. Passed through the
# environment because the subprocess builds its own `Settings` — there is no
# monkeypatching across a process boundary, which is the whole point of the test.
BROWSE_CAP = 2
BOOT_TIMEOUT_SECONDS = 30


def _free_port() -> int:
    """Bind port 0, read what the OS assigned, release it.

    A fixed port would collide with a developer's own running server (:8000 is
    documented as the dev port, and on this machine it is someone else's Docker
    app entirely). The small race between releasing and uvicorn binding is
    acceptable for a single local test and is why boot failure is reported
    explicitly below rather than as a timeout.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_serving(port: int, process: subprocess.Popen) -> None:
    """Poll until the server answers, or fail with whatever it printed.

    Polls a real request rather than sleeping a fixed interval: a fixed sleep is
    either flaky on a slow CI runner or wasted time on a fast one. If the process
    dies during boot, its own stderr is the useful message — a bare timeout here
    would send the next reader hunting for a hang that never happened (the M6
    lesson about diagnosing from evidence rather than from a guess).
    """
    deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = (process.stdout.read() if process.stdout else "") or ""
            pytest.fail(
                f"uvicorn exited during boot with code {process.returncode}:\n{output}"
            )
        try:
            httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1.0)
            return
        except httpx.HTTPError:
            time.sleep(0.15)
    process.kill()
    pytest.fail(f"uvicorn did not start serving on port {port} within {BOOT_TIMEOUT_SECONDS}s")


def _serve(*extra_args: str) -> tuple[subprocess.Popen, int]:
    """Boot a real uvicorn against a throwaway SQLite file."""
    port = _free_port()
    db_path = Path(tempfile.mkdtemp(prefix="nextowner-smoke-")) / "smoke.db"
    env = {
        **os.environ,
        # A temp DB, because a real server runs the startup lifespan and would
        # otherwise create and write the repo's own nextowner.db. `conftest.py`
        # avoids the lifespan entirely; this test cannot, so it redirects instead.
        "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "UPLOAD_DIR": tempfile.mkdtemp(prefix="nextowner-smoke-uploads-"),
        "JWT_SECRET": "smoke-test-secret-not-for-production-0123456789",
        "BROWSE_RATE_LIMIT_MAX": str(BROWSE_CAP),
        # trusted_proxies stays at its default (empty): this test is about an
        # UNTRUSTED client forging the header, which is S3's property carried
        # onto the real server stack.
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
         *extra_args],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_until_serving(port, process)
    except BaseException:
        process.kill()
        raise
    return process, port


def _third_request_status(port: int) -> int:
    """Three browse requests, a different forged X-Forwarded-For on each.

    With a cap of 2, the third request answers the question: 429 means the key
    came from the connection (the header was ignored), 200 means the caller
    minted a fresh counter per request and the limit is evadable.
    """
    statuses = []
    for n in range(3):
        response = httpx.get(
            f"http://127.0.0.1:{port}/api/listings",
            headers={"X-Forwarded-For": f"9.9.9.{n + 1}"},
            timeout=10.0,
        )
        statuses.append(response.status_code)
    assert statuses[0] == 200 and statuses[1] == 200, (
        f"the first two requests must be under the cap, got {statuses}"
    )
    return statuses[2]


@pytest.mark.timeout(120)
def test_s9_proxy_headers_must_be_disabled_for_the_ip_limit_to_hold():
    """S9 — the documented launch flag, actually verified.

    Boots the real server twice with an identical configuration apart from the
    flag, and requires the two to disagree. That disagreement *is* the finding
    from the appsec pass, turned into something that fails a build instead of
    something a reader has to remember.
    """
    guarded, guarded_port = _serve("--no-proxy-headers")
    try:
        guarded_third = _third_request_status(guarded_port)
    finally:
        guarded.kill()
        guarded.wait(timeout=15)

    assert guarded_third == 429, (
        "with --no-proxy-headers a forged X-Forwarded-For must not create a new "
        f"rate-limit bucket, but the 3rd request returned {guarded_third}"
    )

    # The other half: prove the flag is what did that. Uvicorn's default
    # ProxyHeadersMiddleware trusts 127.0.0.1 — which is us — so it rewrites the
    # peer from the header and each forged value becomes its own bucket.
    unguarded, unguarded_port = _serve()
    try:
        unguarded_third = _third_request_status(unguarded_port)
    finally:
        unguarded.kill()
        unguarded.wait(timeout=15)

    assert unguarded_third == 200, (
        "expected the default (proxy-headers-enabled) server to be evadable, so "
        f"that the assertion above is known to depend on the flag; got "
        f"{unguarded_third}. If this fails, uvicorn's defaults have changed — "
        "re-read security.md §9 before relaxing anything, because the guarded "
        "assertion above may now be passing for a different reason."
    )
