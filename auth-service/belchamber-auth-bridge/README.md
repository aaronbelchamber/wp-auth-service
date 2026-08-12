# Belchamber Auth Bridge & Session Storage

> Built by [Aaron Belchamber](https://belchamber.us) — Business Growth & Cloud Systems Architect
> Part of a WordPress plugin family for turning any WP site into a reusable auth/data backend. See also: [wp-auth-service](https://github.com/aaronbelchamber/wp-auth-service) — the standalone auth core this plugin is the WordPress half of.
> More: [Brandager.com](https://brandager.com) · [Belchamber.us](https://belchamber.us) · [Tools.Belchamber.us](https://tools.belchamber.us)

## Description

Turns a WordPress site into a lightweight auth/session backend for other apps, on top of WordPress's own native Application Passwords — no custom login system to build or maintain. Provides:

- Custom DB session storage (`wp_belchamber_auth_sessions`), so an authenticated app doesn't have to re-validate credentials on every request.
- Per-app global (non-PII) key/value data storage.
- REST API endpoints under `/wp-json/auth-bridge/v1/`.
- Rate limiting on those endpoints.
- An admin UI (Application Connections & Auth Service) showing active connections, audit logs, and security settings.

Works standalone — any HTTP client can call its REST endpoints directly with an Application Password. It's commonly paired with [wp-auth-service](https://github.com/aaronbelchamber/wp-auth-service) (a Python/FastAPI service implementing the auth-URL/callback flow), but that pairing is a convenience, not a requirement.

## Installation

1. Upload the `belchamber-auth-bridge` folder to `/wp-content/plugins/`.
2. Activate the plugin through the 'Plugins' menu in WordPress.
3. Configure app whitelisting and owners under **Application Connections & Auth Service** in wp-admin, if desired.

Upgrading from the earlier `wp-app-bridge` plugin name? Activation automatically migrates your existing session tables and whitelist settings forward — see `readme.txt` changelog.

## Requirements

- WordPress 5.6+ (for native Application Passwords support).
- HTTPS (WordPress disables Application Passwords over plain HTTP by default).

## License

GPLv2 or later — see [LICENSE](LICENSE).
