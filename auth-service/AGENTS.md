# Agent Rules & Technical Reference — Auth Service

> [!NOTE]
> This file is **Antigravity IDE agent configuration**. It provides AI agents with instant project guidelines, architecture maps, coding rules, and execution one-liners.

---

## 🎯 Project Overview & Stack

`auth-service` is a dual-mode WordPress authentication & session bridge:
- **`wp_auth_lib/`**: Zero-dependency Python 3.9+ library implementing WordPress Application Passwords auth.
- **`wp_auth_service/`**: FastAPI REST API service wrapping `wp_auth_lib` with API key auth, CORS, and endpoint management.
- **`belchamber-auth-bridge/`**: Single-file WordPress plugin (`belchamber-auth-bridge.php`) providing custom DB session storage (`wp_belchamber_auth_sessions`).
- **`static/`**: Alpine.js + Tailwind web dashboard served directly by FastAPI.

---

## ⚙️ Core Architecture & Rules

### 1. Python OOP Architecture Constraint
- All Python logic inside `wp_auth_service` and helper modules must follow Object-Oriented Programming (OOP) best practices.
- Dependencies are encapsulated inside `ServiceContainer` (`wp_auth_service/container.py`) and attached to `app.state.services`.
- Captured credentials are model-managed inside thread-safe `CredentialStore` (`threading.Lock`).

### 2. WordPress Plugin Versioning Policy
Whenever modifying `belchamber-auth-bridge/belchamber-auth-bridge.php`, run `..\bump-version.ps1 -Plugin belchamber-auth-bridge -Bump patch|minor|major` (from `plugins\`) — do not hand-edit version numbers. It syncs the header `Version:` line and the `BELCHAMBER_AUTH_BRIDGE_VERSION` constant in one step. Bump `BELCHAMBER_AUTH_BRIDGE_DB_VERSION` and its activation-hook `update_option()` call by hand, separately, only when the DB schema actually changed — that's a judgment call the script doesn't make.

---

## 🚀 One-Liner Execution Commands

### Deploy Plugin to Remote Site
```powershell
# Live deployment to tools.belchamber.us (auto-commits to GitHub & uploads via SFTP)
python deploy_plugin.py --plugin belchamber-auth-bridge --site tools-belchamber-us

# Dry-run deployment validation
python deploy_plugin.py --plugin belchamber-auth-bridge --site tools-belchamber-us --dry-run
```

### Run Test Suite
```powershell
python -m pytest tests/
```

### Run Local Service Server
```powershell
python -m wp_auth_service.main
```

---

## 📚 Documentation Index

| File | Description |
|---|---|
| [`README.md`](file:///e:/ab-code-projects/projects/Wordpress/plugins/auth-service/README.md) | High-level project entrypoint & quickstart |
| [`docs/README.md`](file:///e:/ab-code-projects/projects/Wordpress/plugins/auth-service/docs/README.md) | Central Documentation Hub & Table of Contents |
| [`docs/architecture.md`](file:///e:/ab-code-projects/projects/Wordpress/plugins/auth-service/docs/architecture.md) | Detailed architecture, component map & data flow |
| [`docs/deployment.md`](file:///e:/ab-code-projects/projects/Wordpress/plugins/auth-service/docs/deployment.md) | Plugin deployment one-liner & Docker cloud guide |
| [`docs/implementation-log.md`](file:///e:/ab-code-projects/projects/Wordpress/plugins/auth-service/docs/implementation-log.md) | Phased build & implementation history |
| [`docs/admin-auth-guide.md`](file:///e:/ab-code-projects/projects/Wordpress/plugins/auth-service/docs/admin-auth-guide.md) | Site-admin setup: whitelisting, the app-owner connection, `/global` data, rate limits — agent-actionable |
| [`docs/user-auth-guide.md`](file:///e:/ab-code-projects/projects/Wordpress/plugins/auth-service/docs/user-auth-guide.md) | What end users of an app built on this see, and what to do if something goes wrong |
| [`sdks/flutter/auth_kit/README.md`](file:///e:/ab-code-projects/projects/Wordpress/plugins/auth-service/sdks/flutter/auth_kit/README.md) | The Flutter client SDK — integration steps for a new consuming app |
