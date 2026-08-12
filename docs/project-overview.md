# Project Overview

## Goal

Use any WordPress site as a reusable **auth and data-storage backend** for custom app projects — without reinventing auth from scratch for every new app.

The system provides:
- A **zero-config auth flow** using native WordPress Application Passwords (built into WP 5.6+)
- A **lightweight WordPress plugin** (`belchamber-auth-bridge`) that adds a clean session/state storage layer to any WP site
- A **Python library and REST API service** that any app (Python, JS, mobile, CLI) can call to authenticate users and persist app state in WordPress

The design philosophy is **plug-and-play** and **low-maintenance** — auth stays out of the way so development focus stays on the actual app.

---

## Architecture

```
┌──────────────────────────────┐   HTTP Basic Auth (App Password)   ┌──────────────────────────────────┐
│  Custom App (any language)   │ ──────────────────────────────────► │         WordPress Site            │
│                              │                                     │  • Core Auth: /wp-json/wp/v2      │
│  wp_auth_lib  (Python lib)   │ ◄────────────────────────────────── │  • Data API:  /wp-json/auth-bridge/v1     │
│  wp_auth_service (REST API)  │                                     │  • Plugin:    belchamber-auth-bridge       │
└──────────────────────────────┘                                     │  • DB Table:  wp_belchamber_auth_sessions     │
                                                                     └──────────────────────────────────┘
```

**Two sides to the integration:**

- **WordPress side** — the `belchamber-auth-bridge` plugin provisions a `wp_belchamber_auth_sessions` table and exposes REST endpoints for app state CRUD. Authentication is handled entirely by WordPress core (Application Passwords).
- **App side** — `wp_auth_lib` (Python, zero external deps) or the `wp_auth_service` REST API handles the auth URL generation, callback parsing, and credential validation.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| Native WP Application Passwords | Built into WP 5.6+ — no OAuth server, no extra plugins, no maintenance |
| Zero-dependency Python core library | Drops into any Python app without dependency conflicts |
| Dual-mode (library + REST service) | Library for Python apps; service for any language via HTTP |
| Storage-agnostic auth layer | Auth library doesn't persist tokens — consuming apps decide storage strategy |
| Single `wp_belchamber_auth_sessions` table | Flexible JSON payload column avoids schema migrations as apps evolve |
| In-memory cache + optional Redis | Balances simplicity (dev) with scalability (production) |
| API key auth on service endpoints | Simpler than JWT for this scope; sufficient for service-to-service calls |
| FastAPI for REST service | Modern, fast, automatic OpenAPI docs at `/docs` |

---

## Repository Structure

```
plugins/
├── README.md                    ← Monorepo overview & quick start
├── CONTRIBUTING.md              ← Versioning policy & contribution guide
├── docs/
│   └── project-overview.md     ← This file
└── auth-service/
    ├── README.md                ← Full setup & API reference
    ├── ARCHITECTURE.md          ← Component architecture & data flow
    ├── CLOUD_DEPLOYMENT.md      ← Docker / cloud hosting guide
    └── docs/
        └── implementation-log.md ← Phased implementation history
```

---

## WordPress Prerequisites

For the Application Passwords flow to work:

1. **WordPress 5.6+** — Application Passwords are built in.
2. **HTTPS** — WordPress disables Application Passwords over plain HTTP unless `WP_ENVIRONMENT_TYPE` is `local` or `development`.
3. **`belchamber-auth-bridge` plugin** — Required for session/state storage via `/wp-json/auth-bridge/v1/`. Not required for authentication alone.

---

## Local Development Setup

```bash
# 1. Install belchamber-auth-bridge on your WordPress site
#    Copy auth-service/belchamber-auth-bridge/belchamber-auth-bridge.php
#    → wp-content/plugins/ and activate in WP Admin

# 2. Configure and run the auth service
cp auth-service/.env.example auth-service/.env
# Edit .env: set WP_ROOT_URL, APP_NAME, CALLBACK_URL

# Windows
.\auth-service\setup.ps1
# Linux/macOS
./auth-service/setup.sh

# 3. Open the admin UI
# http://localhost:8000
```

---

## Future Directions

- Additional WP data endpoints (user meta, custom post types)
- Multi-site WordPress support
- Token refresh / long-lived session management
- SDKs for JavaScript and mobile (Flutter/Swift)
- Additional Python demo integrations (Flask, Django, FastAPI)
