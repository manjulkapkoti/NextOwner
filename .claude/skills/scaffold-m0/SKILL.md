---
name: scaffold-m0
description: One-time Milestone 0 scaffold — create app/ (Vite react-ts), backend/ (FastAPI + venv), and the root package.json test scripts, then prove the pipeline with GET /health. Only run this once, at the start of the project.
disable-model-invocation: true
---

# Scaffold Milestone 0 — "Hello, FastAPI"

Create the two-app skeleton and prove the whole pipeline end to end with a `GET /health` endpoint. This is heavy, one-time, and creates directories + installs dependencies — **only run when app code does not exist yet.** First check: if `backend/` or `app/` already exist, stop and ask before touching anything.

**`docs/design_implementation.md` §3.3–3.4 and `docs/testing_guide.md` §3 are the source of truth for exact commands.** Read them and follow them; the outline below is the checklist, not a replacement.

## Environment note (Windows)

This machine is Windows 11 with Node 20+ and Python 3.12+. Venv activation is `.venv\Scripts\activate` in cmd/PowerShell. When running via the Bash tool (Git Bash), use `source .venv/Scripts/activate` instead, or just call the venv's binaries directly (`backend/.venv/Scripts/python -m pytest`).

## Steps

1. **Backend** (`backend/`):
   - `python -m venv .venv` and activate it.
   - `pip install "fastapi[standard]" sqlmodel pyjwt bcrypt python-multipart` then `pip install pytest`.
   - `pip freeze > requirements.txt`.
   - Create `backend/app/main.py` with `app = FastAPI(title="NextOwner API")`, routers mounted under the `/api` prefix (WebSockets under `/ws`), and a `GET /api/health` returning `{"status": "ok"}`. Add the throwaway `POST /api/sandbox` (writes a row) + `GET /api/sandbox` (reads it back) from Milestone 0 to prove the DB path.
   - Create `backend/app/db.py` (engine + `get_session` dependency, SQLite file `nextowner.db`).

2. **Frontend** (`app/`):
   - `npm create vite@latest app -- --template react-ts`.
   - `cd app && npm i mobx mobx-react-lite @mui/material @emotion/react @emotion/styled react-router-dom`.
   - Add the single-origin Vite dev proxy to `app/vite.config.ts` (`/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000` with `ws: true`) — no CORS.
   - Add `app/src/lib/api.ts` (fetch wrapper using a **relative** `/api` URL that attaches the JWT header).
   - A React page that calls `GET /api/health` and shows the result.

3. **Root `package.json`** (test orchestration) with scripts:
   ```json
   "test:api":  "cd backend && pytest -q",
   "test:unit": "cd app && vitest run",
   "test:e2e":  "playwright test",
   "test":      "npm run test:api && npm run test:unit"
   ```

4. **Test harness** (`docs/testing_guide.md` §3.4):
   - `cd app && npm i -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom`.
   - Write `backend/tests/conftest.py` (the `session` / `client` / `as_user` / `seed` fixtures — in-memory SQLite via `dependency_overrides`).
   - Write `backend/tests/test_health.py`: `GET /api/health` → 200 `{"status":"ok"}`, and a sandbox row written→read to prove the fixtures.

5. **Prove it:**
   - `cd backend && pytest -q` passes.
   - Optionally start `fastapi dev app/main.py` (Swagger at `http://localhost:8000/docs`) and `npm run dev` (`http://localhost:5173`) to click through once.
   - Confirm `.gitignore` already excludes `.venv/`, `node_modules/`, `nextowner.db`, `backend/uploads/` (it does — check).

6. When green, tell the user the next step: `/new-spec auth-roles` for Milestone 1.
