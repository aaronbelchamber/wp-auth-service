> **Standing preferences apply to this repo.** The operator keeps them in
> cross-project files outside this repository, canonical wherever they and
> anything below disagree. They are not published, and an outside contributor
> does not need them: everything required to build, test and run this project is
> here.

# AGENTS.md

Read MISSION.md for what this project is.

**Status: retired, and not the auth owner.** No site on the drive
runs WordPress any more, so the WordPress-backed auth path this repo provides
has nothing to run against. The drive's auth server is `auth-service-v1`. The
`auth_kit` Flutter SDK is not in this repository: it lives in `auth-service-v1` at
`sdks/flutter/auth_kit`, and the old copy here is removed. Do not develop it here, and do
not restore it.

Three real components live under `auth-service/`: `wp_auth_lib` (zero-dependency Python
core), `wp_auth_service` (FastAPI wrapper), and `belchamber-auth-bridge` (the WordPress
plugin). Handle them as separate concerns despite sharing a repo.

**Dev source of truth is elsewhere.** `auth-service/` here is a public copy of a
private upstream repo, synced by hand (own git history, no automated sync;
`auth-service/check_sync.py` compares two files). Changes belong in the private repo
first, not independently here -- this repo just receives the hand-sync.

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

**Deeper reference**: `docs/project-overview.md` and `auth-service/docs/` (architecture,
deployment, implementation log, auth guides). `.agents/AGENTS.md` (root) and
`auth-service/AGENTS.md` are existing narrower, Antigravity-IDE-scoped config files —
consult those for tool-specific one-liners not duplicated here.
