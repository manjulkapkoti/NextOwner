---
name: open-pr
description: Open a pull request in this project's house style — push the branch, write a body that leads with "What was shipped", create the PR, wait for CI, and present it to the owner in the agreed chat template. Use whenever a PR is being opened or its body edited, including from /run-milestone step 8.
---

# Open a pull request

Two mechanical guards already enforce the rules that *can* be checked
(`.claude/hooks/guard_pr_conventions.py` blocks the command; the
`PR conventions` CI job is the backstop). **This skill owns what they cannot
check: whether the body is worth reading.** A body can pass both guards and
still be a bad PR body.

## The one thing to get right

The PR body records **what shipped**. Nothing else.

The review, the findings, the decisions, the deferrals, the trade-offs, the
"here's what I'd flag" — all of that is *chat*. It is genuinely valuable and the
owner wants it; they want it **in the conversation**, where they can reply, not
embalmed in a PR description nobody re-reads. Putting it in the body is the
single most common way this goes wrong.

## Steps

1. **Confirm the branch is ready.** The work is reviewed and green (`/dod` passed,
   the branch review is clean). A PR means *vetted, ready for a human* — never
   open one to "get eyes on it".

2. **Refresh the three status surfaces first**, if this PR closes a milestone:
   `docs/progress.md`, the `docs/milestones.md` tracker tick, and `CLAUDE.md`'s
   `## Project status:` line. Write them **as they will be true after the merge** —
   not "PR open, awaiting review", which is false the moment it merges and fails
   the `Status freshness` job on `main`. Verify with:
   `python scripts/check_status_freshness.py --force`

3. **Write the body to a file** (not inline — it is long, and quoting breaks in
   PowerShell). Structure:

   ```markdown
   ## What was shipped

   - 3–5 bullets. Each one is something a person can now DO.
   - Plain language. No jargon, no file names, no internal type names.
   - "Anyone can browse live businesses without an account" — not
     "added GET /api/listings with a ListingPublic response_model".

   ## What's in it

   **A bold lead-in label.** Then short prose explaining that piece, one idea
   at a time. Repeat for each meaningful part of the change.

   ## Tests & checks

   The counts, and what the security-relevant coverage actually proves.
   ```

   **Never** include: an attribution footer, a `## Review` / `## Decisions` /
   `## Open questions` / `## Trade-offs` section, or "not merging, awaiting
   approval" boilerplate. The hook blocks most of these; the rule is the point,
   not the regex.

4. **Push and create:**
   ```bash
   git push -u origin <branch>
   gh pr create --base main --title "<title>" --body-file <path>
   ```
   `gh` may not be on PATH — use `"C:\Program Files\GitHub CLI\gh.exe"`.

5. **Wait for CI and do not report until it is green:**
   ```bash
   gh pr checks <n> --watch --interval 20
   ```
   If a check fails, fix it and push again before telling the owner the PR is
   ready. Handing over a red PR wastes their attention on something you already
   knew about. Note that `npm test` locally is **weaker** than CI: CI runs
   `tsc -b` (which typechecks test files) and `eslint`, so run those too.

6. **Present it in chat with exactly this template**, then everything the body
   deliberately excluded:

   ```
   PR URL: <url>
   What changed: <short description>
   Files affected: <list>
   ```

   Follow it with the review outcome, the decisions, anything deferred, and
   anything you want the owner to weigh in on. That material belongs here.

7. **Never merge.** The owner approves and runs `/close-feature`.

## Commit messages

Same rule, same reason: **no `Co-Authored-By: Claude` trailer**, ever. This
overrides the default harness guidance to append one.

Use a message **file** (`git commit -F <path>`) for anything multi-line. The
PowerShell here-string form breaks on parentheses and double quotes — it has
silently produced empty or mangled commits in this repo more than once.

## Why this exists

On PR #36 every commit carried an agent trailer and the body carried an
attribution footer, with the rule already recorded in memory
(`pr-presentation-format`). The rule was fine; recalling it at the right moment
was not. The hook and the CI job now make the mechanical half impossible to get
wrong. This skill carries the half that still takes judgement — and the reason
it is written down is that a body which passes every automated check can still
be the wrong body.
