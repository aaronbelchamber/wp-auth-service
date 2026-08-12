# Contributing Guide

This document covers contribution guidelines and project conventions for this repo — the standalone `wp-auth-service` project (Python auth service + `belchamber-auth-bridge` WordPress plugin).

---

## Plugin Versioning Policy

All changes to `belchamber-auth-bridge` **must** increment the version number. Follow [Semantic Versioning](https://semver.org/):

| Change type | Bump |
|---|---|
| Bug fixes, minor text/doc changes | `patch` (e.g. `1.3.0` → `1.3.1`) |
| New features, backward-compatible | `minor` (e.g. `1.3.0` → `1.4.0`) |
| Breaking changes to DB schema or REST API | `major` (e.g. `1.3.0` → `2.0.0`) |

### Version sync checklist

Every version bump must be reflected in all of these locations:

1. **Plugin file header** in `auth-service/belchamber-auth-bridge/belchamber-auth-bridge.php`:
   ```php
   * Version: X.Y.Z
   ```
2. **PHP constant** `BELCHAMBER_AUTH_BRIDGE_VERSION`:
   ```php
   define('BELCHAMBER_AUTH_BRIDGE_VERSION', 'X.Y.Z');
   ```
3. **PHP constant** `BELCHAMBER_AUTH_BRIDGE_DB_VERSION` *(bump only when the DB schema changes)*, plus the corresponding `update_option()` call in the activation/upgrade hook.
4. **`readme.txt`**'s `Stable tag:` line.

---

## Python Service Versioning

The Python auth service (`wp_auth_service`) does not have a formal version constant. Use git tags for releases:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

---

## Project Structure

See the root [README.md](README.md) for a full repo layout overview and architecture diagram.

---

## Environment Setup

```bash
# Copy environment template
cp auth-service/.env.example auth-service/.env
# Edit .env with your WordPress site details

# Run setup (installs deps + starts service)
# Windows:
.\auth-service\setup.ps1
# Linux/macOS:
./auth-service/setup.sh
```

---

## Documentation Standards

- All documentation lives in tracked `.md` files — no AI session context or tool-specific files in source.
- Shared project-level docs live in `docs/` at the repo root.
- Plugin-specific supplementary docs (deployment guides, implementation logs) live in `auth-service/docs/`.
- Agent-tool configuration (`.agents/AGENTS.md`) is for tool-scoped rules only, not human workflow docs.
- Credential/data-handling policy: [`auth-service/DATA_SECURITY_GOVERNANCE.md`](auth-service/DATA_SECURITY_GOVERNANCE.md).
