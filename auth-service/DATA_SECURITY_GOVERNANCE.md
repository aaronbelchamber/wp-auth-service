# Data Integrity, Safety & Security Governance — auth-service

Scope: `auth-service/` specifically — the one part of this monorepo that handles real credentials (multi-site SSH/deploy access, WordPress Application Passwords). No other plugin here has this concern; see [`plugins/README.md`](../README.md) for the rest.

## 🔒 1. Data Categorization Standard

Every dataset, config file, database table, or cached artifact within `auth-service/` is strictly categorized into one of three security tiers:

| Tier | Category Name | Description & Rules | File / Component Examples |
| :--- | :--- | :--- | :--- |
| **Tier 1** | **Private Local Only** | Sensitive user data, application passwords, active session tokens, local API keys, and site lists containing credentials. **STRICT RULE**: Excluded from git tracking. Must never be committed to public repositories. | `.env`, `wp_auth_service/*.json`, `sites.yaml.example`'s real filled-in counterpart (lives in the separate `site-manager/` repo, not here), `.pytest_cache/`, `__pycache__/` |
| **Tier 2** | **Global App Data** | Schema definitions, configuration templates, non-sensitive demo fixtures, open source plugin code, and public documentation. **RULE**: Tracked in git, fully sanitized of real credentials/PII. | `.env.example`, `sites.yaml.example`, `belchamber-auth-bridge/belchamber-auth-bridge.php`, `wp_auth_lib/`, `wp_auth_service/` |
| **Tier 3** | **System & Transient Cache** | Virtual environments, compiled assets, cache files, test coverage output. **RULE**: Excluded from git tracking. Regenerated dynamically during setup or build. | `venv/`, `*.pyc`, `static/css/style.css` (generated) |

---

## ☁️ 2. Off-Machine Backup & Data Governance

1. **Local Isolation**: All local test environments and configuration credentials (`.env`, `api_keys.json`) remain local-only. The real, filled-in `sites.yaml` used by `deploy_plugin.py` lives in the separate `site-manager` repo at the workspace root, not here — only the sanitized `sites.yaml.example` template is tracked in this repo.
2. **Pre-Release Sanitization**: Production release builds and public repository mirrors MUST use `.example` templates with generic placeholders (`PASSWORD_TOKEN_FROM_CALLBACK`, `http://localhost:8000`).
3. **Database Security**: Session table data stored via `belchamber-auth-bridge` (`wp_belchamber_auth_sessions`) is scoped strictly to authorized WordPress users and sanitized of plaintext passwords.

---

## 📄 3. Security Compliance Verification

- [x] `.gitignore` blocks `.env`, `*.json` storage, `sites.yaml`, and credentials.
- [x] Clean git history free of committed `.env` or live secret keys.
- [x] Complete `.env.example` and `sites.yaml.example` provided for open-source setup.
- [x] Zero hardcoded production passwords or private infrastructure IPs in source files.
