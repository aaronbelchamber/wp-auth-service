# Agent Rules & Technical Reference — Auth Service

> [!NOTE]
> This file is **Antigravity IDE agent configuration**. It provides AI agents with instant project guidelines, architecture maps, coding rules, and execution one-liners.

---

## 🎯 Project Overview & Stack

`auth-service` is a dual-mode WordPress authentication & session bridge:
- **`wp_auth_lib/`**: Zero-dependency Python 3.9+ library implementing WordPress Application Passwords auth.
- **`wp_auth_service/`**: FastAPI REST API service wrapping `wp_auth_lib` with API key auth, CORS, and endpoint management.
- **`wp-app-bridge/`**: Single-file WordPress plugin (`wp-app-bridge.php`) providing custom DB session storage (`wp_app_sessions`).
- **`static/`**: Alpine.js + Tailwind web dashboard served directly by FastAPI.

---

## ⚙️ Core Architecture & Rules

### 1. Python OOP Architecture Constraint
- All Python logic inside `wp_auth_service` and helper modules must follow Object-Oriented Programming (OOP) best practices.
- Dependencies are encapsulated inside `ServiceContainer` (`wp_auth_service/container.py`) and attached to `app.state.services`.
- Captured credentials are model-managed inside thread-safe `CredentialStore` (`threading.Lock`).

### 2. WordPress Plugin Versioning Policy
Whenever modifying `wp-app-bridge/wp-app-bridge.php`, you MUST incrementally bump the plugin version number across:
1. Header constant in `wp-app-bridge.php` (`Version: X.Y.Z`)
2. PHP Constant `WP_APP_BRIDGE_VERSION`
3. PHP Constant `WP_APP_BRIDGE_DB_VERSION` (when DB changes occur)

---

## 🚀 One-Liner Execution Commands

### Deploy Plugin to Remote Site
```powershell
# Live deployment to tools.belchamber.us (auto-commits to GitHub & uploads via SFTP)
python deploy_plugin.py --site tools-belchamber-us

# Dry-run deployment validation
python deploy_plugin.py --site tools-belchamber-us --dry-run
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
