#!/usr/bin/env node
// Cross-platform `npm run test:api` — runs backend pytest with the venv's
// Python whichever venv layout exists (Windows `Scripts/`, POSIX `bin/`),
// falling back to `python` on PATH (what CI uses, where deps are installed
// globally). Replaces the Windows-only `.venv\Scripts\python` npm script so
// the root `npm test` (the DoD gate) works everywhere without activating
// the venv. Requires Node 20.11+ (import.meta.dirname).
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const backend = join(import.meta.dirname, "..", "backend");
const candidates = [
  join(backend, ".venv", "Scripts", "python.exe"), // Windows venv layout
  join(backend, ".venv", "bin", "python"), // POSIX venv layout
];
const python = candidates.find(existsSync) ?? "python";

const result = spawnSync(python, ["-m", "pytest"], {
  cwd: backend,
  stdio: "inherit",
});
if (result.error) {
  console.error(`test:api failed to launch ${python}: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
