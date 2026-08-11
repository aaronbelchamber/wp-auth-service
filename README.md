# WordPress Plugins Monorepo

> Built by [Aaron Belchamber](https://belchamber.us) — Business Growth & Cloud Systems Architect
> A standalone plug-and-play authentication library — no dependency on any other project.
> More: [Brandager.com](https://brandager.com) · [Belchamber.us](https://belchamber.us) · [Tools.Belchamber.us](https://tools.belchamber.us)

A collection of WordPress plugins and companion services built to extend any WordPress site into a **reusable auth and data-storage backend for custom applications**. Everything here is designed to be lightweight, low-maintenance, and plug-and-play — authentication stays out of the way so development focus stays on the apps themselves.

**Quick links:** [Contributing & Versioning](CONTRIBUTING.md) · [Project Overview](docs/project-overview.md) · [Auth Service README](auth-service/README.md) · [Architecture & Design](auth-service/docs/architecture.md)

---

## 📦 Plugins & Services

### [`auth-service/`](auth-service/)

> **WordPress Application Password Authentication Service**

A standalone Python auth service that lets any custom application authenticate its users through a WordPress site using the native [Application Passwords](https://make.wordpress.org/core/2020/11/05/application-passwords-integration-guide/) flow (built into WordPress 5.6+). No custom auth plugin needed on the WordPress side.

| What it does | Details |
|---|---|
| **Auth flow** | Generates WP authorization URLs, parses OAuth-style callbacks, and validates credentials against the WP REST API |
| **Usage modes** | Embedded Python library **or** standalone REST API service |
| **Storage** | Stateless/agnostic — your app handles token persistence |
| **Caching** | In-memory by default; optional Redis for distributed deployments |
| **Admin UI** | Built-in web interface for configuration, API key management, and testing |
| **Cloud ready** | Docker / Docker Compose / AWS / GCP / Azure — see cloud deployment guide |

**Key docs:**

- 📖 [README — Setup & API reference](auth-service/README.md)
- 🏗️ [Architecture & Design](auth-service/docs/architecture.md)
- ☁️ [Cloud Deployment Guide](auth-service/CLOUD_DEPLOYMENT.md)

---

## 🧠 Design Decisions

*The reasoning behind the choices that shape this project — not just what it does, but why it's built this way.*

**Why WordPress Application Passwords instead of a custom OAuth plugin?**

WordPress 5.6+ ships a native Application Passwords flow. Building a parallel OAuth implementation would mean owning token issuance, revocation, and a second attack surface — all logic WordPress core already maintains and patches. Piggybacking on the native flow means zero custom auth code lives on the WordPress side, and every security fix WordPress ships applies automatically.

**Why split the auth logic (`wp_auth_lib`) from the API service (`wp_auth_service`)?**

The library is storage-agnostic and UI-agnostic by design — it never opens a browser, never persists tokens, never assumes an HTTP context. That means it can be embedded directly in a Python app with zero network hop, *or* wrapped in the FastAPI service for non-Python consumers. The dependency rule (`wp_auth_lib` has zero external dependencies) keeps that boundary honest: if the library ever needs a third-party package, that's a signal the boundary has leaked.

**Why is Redis optional rather than required?**

Credential validation is cached to avoid hammering the WordPress REST API on every request. In-memory caching covers the common case (single-instance deployment) with no operational overhead. Redis is a drop-in upgrade for horizontally scaled deployments — the cache interface doesn't change, only the backend. This keeps the barrier to running the service locally at zero while not blocking production scale-out.

---

#### `auth-service/wp-app-bridge/` — WordPress Plugin

> **WP App Bridge & Session Storage** (`v1.2.0`)

A lightweight WordPress plugin (`wp-app-bridge.php`) that sits on the WordPress side of the integration. It provisions a `wp_app_sessions` custom DB table and exposes REST endpoints under `/wp-json/app/v1/` for storing per-user, per-app session/state payloads. Install once on any WP site to give every connected app a clean key-value data store backed by WordPress.

| Feature | Notes |
|---|---|
| **DB provisioning** | Creates `wp_app_sessions` table via `dbDelta()` on activation |
| **REST endpoints** | `GET / POST / DELETE /wp-json/app/v1/session` |
| **Auth** | Piggybacks on WP Application Passwords — no extra auth layer |
| **HTTPS compatibility** | Handles reverse proxy / Cloudflare HTTPS detection automatically |
| **Application Passwords** | Force-enables the feature regardless of environment type |

---

#### `auth-service/wp_auth_lib/` — Python Library

Zero-dependency Python package (stdlib only) for the auth flow:

| Module | Responsibility |
|---|---|
| `auth.py` | `generate_auth_url`, `parse_callback_url`, `validate_credentials` |
| `types.py` | Typed dataclasses — `WPUser`, `AuthResult`, `AppSession` |
| `exceptions.py` | `WPConnectionError`, `WPAuthError`, `WPApiError`, `WPDataError` |
| `cache.py` | In-memory validation caching with optional Redis backend |

---

#### `auth-service/wp_auth_service/` — REST API Service

FastAPI-based service layer that wraps `wp_auth_lib` and exposes it as a network-accessible REST API, with an admin web UI and API key management.

**Endpoints:**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/url` | Generate WP authorization URL |
| `POST` | `/api/v1/auth/callback` | Parse callback and extract credentials |
| `POST` | `/api/v1/auth/validate` | Validate credentials with WordPress |
| `GET/POST` | `/api/v1/config` | Read / write service configuration |
| `GET/POST/DELETE` | `/api/v1/api-keys` | API key lifecycle management |

Interactive docs: `http://localhost:8000/docs` (when running locally)

---

## 🏗️ Architecture at a Glance

```
┌──────────────────────────────┐   HTTP Basic Auth (App Password)   ┌──────────────────────────────────┐
│  Custom App (any language)   │ ──────────────────────────────────► │         WordPress Site            │
│                              │                                     │  • Core Auth: /wp-json/wp/v2      │
│  wp_auth_lib  (Python)       │ ◄────────────────────────────────── │  • Data API:  /wp-json/app/v1     │
│  wp_auth_service (REST API)  │                                     │  • Plugin:    wp-app-bridge       │
└──────────────────────────────┘                                     │  • DB Table:  wp_app_sessions     │
                                                                     └──────────────────────────────────┘
```

**Auth flow summary:**

1. App calls `/api/v1/auth/url` → gets a WP authorization URL
2. User clicks link, logs into WordPress, approves the app
3. WordPress redirects back with credentials in the callback URL
4. App calls `/api/v1/auth/callback` → extracts `user_login` + `app_password`
5. App calls `/api/v1/auth/validate` → verifies credentials, returns user profile
6. App stores credentials and uses them for subsequent calls to `/wp-json/app/v1/session`

For the full component breakdown and error-handling model, see **[Architecture & Design](auth-service/docs/architecture.md)**.

---

## ⚡ Quick Start

### 1. Install the WordPress Plugin

Copy `auth-service/wp-app-bridge/wp-app-bridge.php` into your WordPress site's `wp-content/plugins/` directory and activate it from WP Admin.

### 2. Run the Auth Service

**Windows:**
```powershell
cd auth-service
.\setup.ps1
```

**Linux / macOS:**
```bash
cd auth-service
./setup.sh
```

Open `http://localhost:8000` to configure your WordPress site URL and generate API keys.

### 3. Connect Your App

```python
from wp_auth_lib import generate_auth_url, parse_callback_url, validate_credentials

auth_url = generate_auth_url(
    wp_root_url="https://your-site.com",
    app_name="My App",
    callback_url="https://myapp.com/callback"
)
# Direct the user to auth_url, then handle the callback...
```

For full library and REST API usage see **[auth-service/README.md](auth-service/README.md)**.

---

## ⚙️ Configuration

All configuration lives in `auth-service/.env`. Copy `.env.example` to get started:

```bash
cp auth-service/.env.example auth-service/.env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `WP_ROOT_URL` | ✅ | — | Your WordPress site root URL |
| `APP_NAME` | ✅ | — | Identifier shown during authorization |
| `CALLBACK_URL` | ✅ | — | Where WP redirects after user approves |
| `API_KEY` | No | — | Default API key (or generate via UI) |
| `CACHE_TTL` | No | `300` | Validation cache TTL in seconds |
| `REDIS_URL` | No | — | Redis connection string (distributed cache) |
| `CORS_ORIGINS` | No | `*` | Restrict CORS in production |
| `SERVICE_PORT` | No | `8000` | Port the service listens on |

---

## 🔒 Security Notes

- **HTTPS required** — WordPress disables Application Passwords over plain HTTP unless `WP_ENVIRONMENT_TYPE` is set to `local` or `development`.
- **Always use API keys** — protect all service endpoints in any non-local environment.
- **Restrict CORS** — set `CORS_ORIGINS` to your app's domain(s) in production.
- **Never commit `.env`** — it is already in `.gitignore`.
- **Rotate credentials** — revoke and regenerate Application Passwords and API keys periodically.

---

## 📁 Repo Layout

```
plugins/
├── README.md                        ← you are here
├── CONTRIBUTING.md                  ← Versioning policy & contribution guidelines
├── docs/
│   └── project-overview.md         ← Project goals, design decisions, future directions
├── auth-service/                    ← Auth service root
│   ├── README.md                    ← Full setup & API reference
│   ├── docs/architecture.md         ← Component architecture & data flow
│   ├── CLOUD_DEPLOYMENT.md          ← Docker / cloud hosting guide
│   ├── setup.ps1 / setup.sh         ← One-command setup scripts
│   ├── requirements.txt
│   ├── .env.example
│   ├── docs/
│   │   └── implementation-log.md   ← Phased build history
│   ├── wp-app-bridge/
│   │   └── wp-app-bridge.php        ← WordPress plugin (install on WP site)
│   ├── wp_auth_lib/                 ← Zero-dependency Python library
│   │   ├── auth.py
│   │   ├── types.py
│   │   ├── exceptions.py
│   │   └── cache.py
│   ├── wp_auth_service/             ← FastAPI REST service
│   │   ├── main.py
│   │   ├── config.py
│   │   └── api/
│   ├── static/                      ← Admin web UI
│   ├── deployment/                  ← Docker Compose & cloud configs
│   └── tests/
└── .agents/
    └── AGENTS.md                    ← Agent-tool configuration (Antigravity IDE)
```

---

## 🗺️ Roadmap

This repo is under active development. See [`auth-service/docs/implementation-log.md`](auth-service/docs/implementation-log.md) for the full phased build history.

| Stage | Goal | Status |
|---|---|---|
| 1 | WP Plugin — DB table + REST endpoints | ✅ Complete |
| 2 | Python Auth & Data Bridge (`wp_auth_lib`) | ✅ Complete |
| 3 | Diagnostics & Error Handling | ✅ Complete |
| 4 | App Integration Pattern & Cloud Readiness | ✅ Complete |
| 5 | Documentation & Architecture | ✅ Complete |
| 6 | WP App Bridge Plugin & Session Storage (`v1.2.0`) | ✅ Complete |

---

## 🍴 Fork & Self-Host

This project is designed to be forked, customized, and self-hosted. Clone it to your own Git provider and make it yours.

### GitHub

```bash
# 1. Fork via the GitHub UI, or clone directly:
git clone https://github.com/aaronbelchamber/wp-auth-service.git my-auth-service
cd my-auth-service

# 2. Point to your own remote:
git remote set-url origin https://github.com/<your-username>/my-auth-service.git

# 3. Push:
git push -u origin main
```

### After Forking

1. **Configure your site** — Copy `.env.example` to `.env` and set your WordPress URL, app name, and callback.
2. **Deploy the WP plugin** — Copy `auth-service/wp-app-bridge/wp-app-bridge.php` to your WordPress site's `wp-content/plugins/` and activate it.
3. **Run the service** — `cd auth-service && ./setup.sh` (or `.\setup.ps1` on Windows).
4. **Customize deployment** — Edit `deploy_plugin.py` or `deploy_plugin.ps1` to point to your own servers. Create a `sites.yaml` based on `sites.yaml.example` for multi-site deployments.

> [!TIP]
> The deploy scripts reference `site-manager` config files (`sites.yaml`, `credentials.enc`). If you don't use `site-manager`, set the `WP_DEPLOY_*` environment variables instead — see [`auth-service/README.md`](auth-service/README.md) for details.

---

## 🤝 Contributing

Contributions, bug reports, and feature requests are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for versioning policy and guidelines.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
