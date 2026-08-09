# Auth Service — Architecture & Design

## Overview

The WordPress Auth Service is a dual-mode authentication and session bridge. It uses native WordPress Application Passwords (built into WP 5.6+) as the identity provider and exposes the auth flow as either an embeddable Python library or a standalone REST API service.

---

## Component Layout

```
plugins/
└── auth-service/
    ├── wp_auth_lib/          ← Core Python library (zero external deps)
    ├── wp_auth_service/      ← FastAPI REST service (wraps wp_auth_lib)
    ├── wp-app-bridge/        ← WordPress plugin (installs on WP site)
    └── static/               ← Admin web UI (Alpine.js)
```

---

## Component Boundaries

### `wp_auth_lib` — Core Library

**Responsibility:** Implement the WordPress Application Passwords auth flow using Python's standard library only (`urllib`, `base64`, `json`).

**Key principle:** The library is **storage-agnostic and UI-agnostic**. It never opens a browser, never persists tokens, and never manages state. It takes inputs and returns structured results — the consuming app decides what to do with them.

| Module | Exports | Responsibility |
|---|---|---|
| `auth.py` | `generate_auth_url()`, `parse_callback_url()`, `validate_credentials()` | Core auth flow |
| `types.py` | `UserProfile`, `AuthConfig`, `CallbackResult` | Typed dataclasses |
| `exceptions.py` | `WPConnectionError`, `WPAuthError`, `WPApiError`, `WPDataError` | Explicit error classes |
| `cache.py` | `CredentialCache` | TTL validation cache; Redis adapter |

**Dependency rule:** `wp_auth_lib` has **zero external dependencies**. It must remain importable in any Python 3.9+ environment without `pip install`.

---

### `wp_auth_service` — REST API Service

**Responsibility:** Wrap `wp_auth_lib` in a FastAPI HTTP server so any language/platform can call the auth flow over HTTP.

**Key principle:** The service layer owns API key management, CORS policy, and configuration persistence. Business logic lives in `wp_auth_lib`, not here.

```
wp_auth_service/
├── main.py            ← FastAPI app bootstrap, lifespan, static file mounting
├── container.py       ← ServiceContainer, ActivityLogger, CredentialStore
├── config.py          ← Env-based config (WP_ROOT_URL, APP_NAME, etc.)
├── storage.py         ← API key file storage
├── endpoint_storage.py← Registered endpoint storage
├── activity_storage.py← Activity log storage
└── api/
    ├── routes.py      ← Auth + config + key management endpoints
    └── middleware.py  ← X-API-Key header enforcement
```

**API Surface:**

| Endpoint | Auth required | Purpose |
|---|---|---|
| `POST /api/v1/auth/url` | Yes | Generate WP authorization URL |
| `POST /api/v1/auth/callback` | No | Parse callback, extract credentials |
| `POST /api/v1/auth/validate` | Yes | Validate credentials with WP |
| `GET/POST /api/v1/config` | Yes | Read / write service config |
| `GET/POST/DELETE /api/v1/api-keys` | Yes | API key lifecycle |

Interactive OpenAPI docs: `http://localhost:8000/docs`

---

### `wp-app-bridge` — WordPress Plugin

**Responsibility:** Add a session/state storage layer to any WordPress site without touching WP core or existing content.

**Key principle:** Authentication is 100% handled by WordPress core (Application Passwords). The plugin only handles data — it never reimplements auth.

```
wp-app-bridge/
└── wp-app-bridge.php   ← Single-file plugin (all logic self-contained)
```

**What the plugin does:**
1. On activation: provisions `wp_app_sessions` table via `dbDelta()`
2. Registers REST routes under namespace `app/v1`
3. Sets `permission_callback => 'is_user_logged_in'` on all routes (WP core validates the Application Password in the `Authorization: Basic` header automatically)
4. Detects reverse proxy / Cloudflare HTTPS so Application Passwords work behind load balancers
5. Force-enables Application Passwords (`wp_is_application_passwords_available` filter) regardless of environment type — safe for local HTTP development

---

### `static/` — Admin Web UI

**Responsibility:** Provide a browser-based interface for first-run configuration, API key generation, and live auth flow testing.

**Technology:** Alpine.js (no build step), Tailwind CSS (CDN). The UI is served directly by `wp_auth_service/main.py` as static files — no separate web server needed.

---

## Authentication Data Flow

```
1. App → POST /api/v1/auth/url
         body: { wp_root_url, app_name, callback_url }
         ↓
2. Service → wp_auth_lib.generate_auth_url()
         returns: { auth_url: "https://site.com/wp-admin/authorize-application.php?..." }
         ↓
3. User opens auth_url in browser
   → logs into WordPress
   → approves the app
   ↓
4. WordPress redirects to callback_url?user_login=...&password=...
         ↓
5. App → POST /api/v1/auth/callback
         body: { callback_url: "<full redirect URL>" }
         ↓
6. Service → wp_auth_lib.parse_callback_url()
         returns: { user_login, password }
         ↓
7. App → POST /api/v1/auth/validate
         body: { user_login, password, wp_root_url }
         ↓
8. Service → wp_auth_lib.validate_credentials()
         → GET {wp_root_url}/wp-json/wp/v2/users/me  (HTTP Basic Auth)
         returns: { user_id, username, email, roles, capabilities }
         ↓
9. App stores credentials and uses them for subsequent calls:
         GET/POST/DELETE {wp_root_url}/wp-json/app/v1/session
         Authorization: Basic base64(user_login:password)
```

---

## Error Handling

All errors surface as typed exceptions from `wp_auth_lib/exceptions.py`:

| Exception | When raised |
|---|---|
| `WPConnectionError` | DNS failure, network timeout, connection refused |
| `WPAuthError` | Invalid credentials, revoked Application Password, HTTPS required |
| `WPApiError` | WP REST API unavailable, `wp-app-bridge` plugin not installed |
| `WPDataError` | DB query failure, malformed JSON payload |

The REST service translates these to appropriate HTTP status codes with descriptive JSON error bodies.
