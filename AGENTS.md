> **Standing preferences apply to this repo.** The operator of this project
> keeps them outside this repository, in four cross-project files —
> `PREFERENCES.md` (ports, launching processes without a window, URL hygiene,
> hosting), `PRACTICES.md` (script placement, file size, verification, design
> systems, self-review, CI), `COLLABORATION.md` (version control and branch
> conventions, worktrees rather than `main`) and `DOCUMENTATION.md` (writing a
> doc in the tense of what exists, session retros). All four are canonical
> where they and anything below disagree.
>
> They are not published here, and they are not something an outside
> contributor needs: everything required to build, test and run this project is
> in this repo. If you are working with the drive mounted they are in
> `E:\project-hub\` — read all four before changing anything.

# AGENTS.md

Read MISSION.md for what this project is.

Three real components live under `auth-service/`: `wp_auth_lib` (zero-dependency Python
core), `wp_auth_service` (FastAPI wrapper), and `belchamber-auth-bridge` (the WordPress
plugin) — plus the Flutter client SDK at `auth-service/sdks/flutter/auth_kit`. Handle
them as separate concerns despite sharing a repo.

**Dev source of truth is elsewhere.** MISSION.md's "Related projects" section states
`auth-service/` here is a published copy of a private upstream repo.
Changes belong in the private repo first, not independently here — this repo just
receives the sync.

**Run the service**: `cd auth-service`, then `.\setup.ps1` / `./setup.sh` (installs deps,
writes config, starts on `http://localhost:8000`, admin UI + `/docs`). Manual: `pip
install -r requirements.txt`, `cp .env.example .env`, `python -m wp_auth_service.main`.
`start_dev.ps1` is the dev-loop variant.

**Tests**: `python -m pytest tests/` from `auth-service/` (four files: plugin bridge,
endpoint storage, service integration, storage lifecycle). No `.github/workflows/` exists,
so nothing runs these in CI — run them yourself before marking work done. No Python
lint/format config found either (no ruff/black/flake8).

**belchamber-auth-bridge**: single PHP file, no build step. Deploy with `python
deploy_plugin.py --site tools-belchamber-us` (commits + SFTP upload), `--dry-run` to
check only. Every plugin change MUST bump the version, synced by hand across: header
`Version:`, `BELCHAMBER_AUTH_BRIDGE_VERSION` constant, `readme.txt`'s `Stable tag:`, and
— schema changes only — `BELCHAMBER_AUTH_BRIDGE_DB_VERSION` plus its activation-hook
`update_option()` call. Policy detail: `CONTRIBUTING.md`. The `bump-version.ps1` helper
referenced in `auth-service/AGENTS.md` is private-repo tooling, not present here — sync
by hand.

**auth_kit**: `auth-service/sdks/flutter/auth_kit`, Dart `^3.12.0` / Flutter `>=3.24.0`.
`flutter test` and `flutter analyze` (has `flutter_lints`) from that directory; not wired
into CI.

**Deeper reference**: `docs/project-overview.md` and `auth-service/docs/` (architecture,
deployment, implementation log, auth guides). `.agents/AGENTS.md` (root) and
`auth-service/AGENTS.md` are existing narrower, Antigravity-IDE-scoped config files —
consult those for tool-specific one-liners not duplicated here.
