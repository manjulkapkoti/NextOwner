#!/usr/bin/env node
// Cross-platform `npm run lint:api` — runs Ruff with the venv's Python whichever
// venv layout exists (Windows `Scripts/`, POSIX `bin/`), falling back to
// `python` on PATH (what CI uses). Mirrors scripts/test-api.mjs.
// Requires Node 20.11+ (import.meta.dirname).
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const backend = join(import.meta.dirname, "..", "backend");
const candidates = [
  join(backend, ".venv", "Scripts", "python.exe"), // Windows venv layout
  join(backend, ".venv", "bin", "python"), // POSIX venv layout
];
const python = candidates.find(existsSync) ?? "python";

const result = spawnSync(python, ["-m", "ruff", "check", "app", "tests"], {
  cwd: backend,
  stdio: "inherit",
});
if (result.error) {
  console.error(`lint:api failed to launch ${python}: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
