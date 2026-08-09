# Contributing Guide

This document covers contribution guidelines and project conventions for this monorepo.  
It is the authoritative reference for all contributors — human or automated.

---

## Plugin Versioning Policy

All changes to the `wp-app-bridge` WordPress plugin **must** increment the version number. Follow [Semantic Versioning](https://semver.org/):

| Change type | Bump |
|---|---|
| Bug fixes, minor text/doc changes | `patch` (e.g. `1.2.0` → `1.2.1`) |
| New features, backward-compatible | `minor` (e.g. `1.2.0` → `1.3.0`) |
| Breaking changes to DB schema or REST API | `major` (e.g. `1.2.0` → `2.0.0`) |

### Version sync checklist

Every version bump must be reflected in **all four** of these locations:

1. **Plugin file header** in `auth-service/wp-app-bridge/wp-app-bridge.php`:
   ```php
   * Version: X.Y.Z
   ```
2. **PHP constant** `WP_APP_BRIDGE_VERSION`:
   ```php
   define('WP_APP_BRIDGE_VERSION', 'X.Y.Z');
   ```
3. **PHP constant** `WP_APP_BRIDGE_DB_VERSION` *(bump only when the DB schema changes)*:
   ```php
   define('WP_APP_BRIDGE_DB_VERSION', 'X.Y.Z');
   ```
4. **Activation/update hook** — ensure `update_option('wp_app_bridge_db_version', WP_APP_BRIDGE_DB_VERSION)` is called when the DB version changes.

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

## Adding a New Plugin

When adding a new plugin directory to this monorepo:

1. Create `your-plugin/README.md` documenting setup, endpoints, and configuration.
2. Add a section to the root `README.md` under **Plugins & Services**.
3. Add the plugin directory to the repo layout tree in root `README.md`.
4. If the plugin has a WordPress PHP component, follow the versioning policy above.

---

## Documentation Standards

- All documentation lives in tracked `.md` files — no AI session context or tool-specific files in source.
- Each plugin has its own `README.md` at its root.
- Shared project-level docs live in `docs/` at the repo root.
- Plugin-specific supplementary docs (deployment guides, implementation logs) live in `<plugin>/docs/`.
- Agent-tool configuration (`.agents/AGENTS.md`) is for tool-scoped rules only, not human workflow docs.
