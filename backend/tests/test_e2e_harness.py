"""M13 — spec 013, the E2E harness: the hermetic run and the admin CLI.

Two kinds of test live here, and the difference matters when reading them:

- **H2/H3/H4 are ordinary functional tests** of ``seed/make_admin.py``, the one
  artefact in this milestone that grants privilege. They invoke it the way a
  shell does and assert on what it refuses.
- **H1/H5 pin configuration.** They parse ``playwright.golden.config.ts`` and
  ``ci.yml`` and assert properties that no runtime test can observe from inside
  the process those files configure. That is the same shape as
  ``check_status_freshness.py`` and ``check_pr_conventions.py``: a claim whose
  only enforcement point is the file itself.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CONFIG = ROOT / "app" / "playwright.golden.config.ts"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _load_e2e_serve():
    """Import `scripts/e2e_serve.py` by path — it is a script, not a package.

    Safe to import: everything that opens a socket or a database lives inside
    `main()`, so module import is pure definitions.
    """
    spec = importlib.util.spec_from_file_location("e2e_serve", ROOT / "scripts" / "e2e_serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_make_admin(*args: str, env_extra: dict[str, str] | None = None, cwd: Path | None = None):
    """Invoke the CLI as a shell would, so the test exercises the real entry point."""
    import os

    env = dict(os.environ)
    env.pop("NEXTOWNER_ALLOW_ADMIN_PROMOTION", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "seed.make_admin", *args],
        cwd=str(cwd or ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


# ── H1: the run is hermetic ──────────────────────────────────────────────────

def test_h1_golden_config_binds_a_dedicated_database():
    """H1 — the golden run must never touch the developer's nextowner.db.

    Asserted against the config rather than by running the suite: the property
    is "this file points the backend somewhere else", and the only place that
    can be checked is the file. A run that used nextowner.db would still pass
    every G criterion while destroying local data, which is precisely why this
    needs its own criterion.
    """
    assert GOLDEN_CONFIG.exists(), f"{GOLDEN_CONFIG} does not exist"
    config = GOLDEN_CONFIG.read_text(encoding="utf-8")

    database_urls = re.findall(r"DATABASE_URL\s*[:=]\s*['\"]([^'\"]+)['\"]", config)
    assert database_urls, "the golden config must set DATABASE_URL for its backend server"
    for url in database_urls:
        assert "nextowner.db" not in url, f"golden run would write to the dev database: {url}"
        assert "e2e" in url, f"expected a dedicated e2e database, got: {url}"

    # Deleted before the run, or the second run inherits the first one's rows
    # and every "unique headline" assumption in the path quietly stops holding.
    assert re.search(r"globalSetup", config), "the golden config must declare a globalSetup"

    # Reusing a running server means reusing its database (spec 013 D7).
    assert re.search(r"reuseExistingServer\s*:\s*false", config), (
        "the golden config must not reuse an existing server"
    )

    # ── and the guard that actually makes the claim true ────────────────────
    #
    # Everything above reads the config's *intent*. H1 promises something
    # stronger — that the developer's database is untouched — and the only code
    # that can keep that promise is `_sqlite_path`, which decides what gets
    # deleted. It had no direct test until the independent appsec pass
    # (2026-08-03) showed the original hand-rolled parser accepting
    # `sqlite:///nextowner.db?e2e=1`: refused by nothing here, opened as the
    # real `nextowner.db` by SQLAlchemy. A guard that parses its input
    # differently from the thing it guards is not a guard.
    e2e_serve = _load_e2e_serve()
    outside_the_repo = (Path(tempfile.gettempdir()) / "e2e-notes.db").as_posix()

    hostile = [
        "sqlite:///nextowner.db",                              # the obvious one
        "sqlite:///../nextowner.db",                           # ...via a relative path
        "sqlite:///nextowner.db?e2e=1",                        # the parser differential
        "sqlite:///file:nextowner.db?uri=true&mode=rwc&e2e=1",  # SQLite's URI grammar
        "postgresql://user:pw@localhost:5432/nextowner",       # not SQLite at all
        "sqlite://",                                           # names no file
        "sqlite:///:memory:",
        f"sqlite:///{outside_the_repo}",                       # right name, wrong place
        "sqlite:///scratch.db",                                # not named like a throwaway
    ]
    for url in hostile:
        with pytest.raises(SystemExit):
            e2e_serve._sqlite_path(url)

    # ...and the one it must still accept, or the harness cannot run at all.
    accepted = (ROOT / "backend" / "e2e.db").as_posix()
    assert e2e_serve._sqlite_path(f"sqlite:///{accepted}").name == "e2e.db"


# ── H2/H3/H4: the admin CLI refuses what it should ───────────────────────────

def test_h2_make_admin_refuses_a_user_that_does_not_exist(tmp_path):
    """H2 — promote-only. The CLI must never be able to create a principal."""
    db = tmp_path / "e2e-h2.db"
    result = _run_make_admin(
        "nobody@e2e.test",
        env_extra={
            "DATABASE_URL": f"sqlite:///{db}",
            "NEXTOWNER_ALLOW_ADMIN_PROMOTION": "1",
        },
    )

    assert result.returncode != 0, "promoting a non-existent user must fail"
    assert "register" in (result.stdout + result.stderr).lower(), (
        "the refusal should tell the operator the user must register first"
    )

    # And it must not have created the row as a side effect.
    if db.exists():
        from app.models import User

        from sqlalchemy import create_engine

        engine = create_engine(f"sqlite:///{db}")
        with Session(engine) as session:
            assert session.exec(select(User).where(User.email == "nobody@e2e.test")).first() is None

    # "Creates nothing" has to hold for every spelling of a SQLite URL, not just
    # the one the guard was written against. `sqlite+pysqlite:///` used to pass
    # the dialect check and skip the existence check entirely, so it created a
    # zero-byte file and then died in a raw OperationalError traceback rather
    # than this CLI's plain refusal (appsec pass, 2026-08-03).
    ghost = tmp_path / "e2e-ghost.db"
    result = _run_make_admin(
        "nobody@e2e.test",
        env_extra={
            "DATABASE_URL": f"sqlite+pysqlite:///{ghost}",
            "NEXTOWNER_ALLOW_ADMIN_PROMOTION": "1",
        },
    )
    assert result.returncode != 0
    assert not ghost.exists(), "make_admin created a database file it was only asked to read"
    assert "Traceback" not in result.stderr, (
        "the operator should get the CLI's refusal, not a SQLAlchemy stack trace"
    )


def test_h3_make_admin_refuses_a_non_sqlite_database(tmp_path):
    """H3 — a Postgres URL means something closer to production, and that path
    deserves a deliberate decision rather than this script. Same guard
    ``seed/seed.py`` already carries, for the same reason."""
    result = _run_make_admin(
        "someone@e2e.test",
        env_extra={
            "DATABASE_URL": "postgresql://user:pw@localhost:5432/nextowner",
            "NEXTOWNER_ALLOW_ADMIN_PROMOTION": "1",
        },
    )

    assert result.returncode != 0, "a non-SQLite database URL must be refused"
    assert "sqlite" in (result.stdout + result.stderr).lower()


def test_h4_make_admin_refuses_without_the_explicit_opt_in(tmp_path):
    """H4 — it cannot run by accident. The opt-in is the whole reason this is a
    CLI and not an endpoint: `security.md` §6 names test-only backdoors as a
    threat, and a tool that grants admin on a bare invocation is one."""
    db = tmp_path / "e2e-h4.db"
    result = _run_make_admin(
        "someone@e2e.test",
        env_extra={"DATABASE_URL": f"sqlite:///{db}"},
    )

    assert result.returncode != 0, "running without the opt-in must be refused"
    assert "NEXTOWNER_ALLOW_ADMIN_PROMOTION" in (result.stdout + result.stderr)


# ── H5: the suite is actually enforced ───────────────────────────────────────

def test_h5_ci_runs_the_golden_path_as_a_blocking_job():
    """H5 — an E2E nobody runs is decoration.

    `ci.yml` already records the reasoning for the sibling browser job: "without
    this the Playwright suite only runs when someone remembers, and an unrun
    test rots." This pins that the golden path got the same treatment, and that
    nobody later softened it into an advisory check.
    """
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "playwright.golden.config.ts" in workflow, (
        "no CI job runs the golden-path config"
    )

    # Locate the job that runs it, and read only that job's block.
    lines = workflow.splitlines()
    run_line = next(i for i, line in enumerate(lines) if "playwright.golden.config.ts" in line)
    job_start = next(
        i for i in range(run_line, -1, -1)
        if re.match(r"^  [a-z0-9_-]+:\s*$", lines[i])
    )
    job_end = next(
        (i for i in range(job_start + 1, len(lines)) if re.match(r"^  [a-z0-9_-]+:\s*$", lines[i])),
        len(lines),
    )
    job = "\n".join(lines[job_start:job_end])

    assert "continue-on-error" not in job, "the golden-path job must block, not advise"
    # A job conditioned off pull_request would leave every PR unguarded — the
    # exact hole `status-freshness` and `pr-conventions` are allowed to have and
    # this one is not.
    #
    # Anchored at the JOB's indent (four spaces), not `^\s*if:`. The looser
    # pattern also matched the step-level `if: failure()` that gates the
    # report upload — a conditional that decides whether to keep an artefact,
    # not whether to run the suite. Reading it as the second thing put this
    # criterion in conflict with the milestone's own § Errors & failure modes,
    # which requires that upload. The criterion says "a conditional that skips
    # it on pull requests"; only a job-level `if:` can do that.
    conditional = re.search(r"^    if:\s*(.+)$", job, re.MULTILINE)
    if conditional:
        assert "pull_request" in conditional.group(1), (
            f"the golden-path job skips pull requests: if: {conditional.group(1)}"
        )


@pytest.mark.parametrize("path", [GOLDEN_CONFIG, CI_WORKFLOW])
def test_harness_files_are_readable(path):
    """A guard on the guards: if either file moves, H1/H5 would pass vacuously
    on a `.exists()` that nobody asserted."""
    assert path.exists(), f"{path} is missing — H1/H5 cannot mean anything without it"
