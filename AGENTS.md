# AGENTS.md

## Repo state
- Fresh scaffold at `0deb120` on `main` (empty `readme.md`); now 37 skills installed.
- No `package.json`, lockfile, build/test/lint/typecheck config, or `opencode.json` detected. Do not assume npm/pnpm/yarn, test runner, or build command — verify with `Get-ChildItem -Force -Recurse` before adding toolchain claims.
- Remote `origin` is `https://github.com/Vighnesh-V-H/voic.git` (`main` branch).

## Structure
- `readme.md` — empty, no project description yet.
- `.agents/skills/` — 37 skills from `mattpocock/skills` (engineering + productivity + misc).
- `docs/agents/` — `issue-tracker.md` (GitHub) + `domain.md` (single-context `CONTEXT.md` + `docs/adr/`) + `triage-labels.md`; `CONTEXT.md`/`CONTEXT-MAP.md`/`docs/adr/` not yet created (lazy via `/domain-modeling`).
- `skills-lock.json:1` — tracks 37 installed skills.

## Commands
- Frontend verification: run `npm run lint` and `npm run build` from `apps/frontend`.
- Backend verification: run `.venv\Scripts\python.exe -m pytest -q` and `.venv\Scripts\python.exe -m compileall -q app migrations tests` from `apps/backend`.
- Backend migration verification: run `.venv\Scripts\python.exe -m alembic upgrade head` from `apps/backend` against a configured PostgreSQL database; use `.venv\Scripts\python.exe -m alembic upgrade head --sql` for offline generation.
- Run one backend test with `.venv\Scripts\python.exe -m pytest tests/test_auth.py -q` from `apps/backend`.

## Workflow
- Branch: `main` tracks `origin/main`. Check `git status` / `git diff` before committing; stage only intended files.
- No CI workflows, pre-commit hooks, or task runner config found.
- For GitHub operations use `gh` CLI — repo inferred from `git remote -v`.

## Task and branch workflow
- Assess the size of every ticket or feature before implementation.
- Keep a ticket that fits one focused implementation session on one dedicated branch.
- Create a new branch for every ticket or feature; do not implement ticket work directly on `main`.
- When a ticket is too large for one focused implementation session, split it into smaller, independently verifiable tickets before coding.
- Give each split ticket its own branch and record the dependency order between those branches or tickets.
- Prefer branches named `feature/<ticket-id>-<short-slug>` for features and `fix/<ticket-id>-<short-slug>` for fixes.

## Agent skills

### Issue tracker

GitHub Issues for `Vighnesh-V-H/voic` via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default 5 labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.

## Windows / OpenCode quirks
- Shell is Windows PowerShell 5.1 (`win32`). Do not use `&&`; chain with `cmd1; if ($?) { cmd2 }`. Quote paths with spaces. Prefer `workdir` param over `Set-Location`.
- Use `C:\Users\vighnesh\AppData\Local\Temp\opencode` for temp work outside workspace.
- Prefer dedicated tools over shell for file ops: `read`/`glob`/`grep`/`edit`/`write`.
