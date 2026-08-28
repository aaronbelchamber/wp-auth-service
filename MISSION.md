# Mission

wp-auth-service is a standalone authentication provider that lets any custom app -- Python, JS, mobile, CLI -- authenticate its users through a WordPress site, using WordPress's own native Application Passwords (built into WP 5.6+) instead of a hand-rolled login system. It solves one problem: don't build and maintain auth from scratch for every new app when a WordPress site can already do credential validation. It is for anyone running a WordPress site who is building apps beside it and would rather not own an auth stack per app.

## What this is for

- A Python auth core (`wp_auth_lib`, zero external dependencies) that generates the WP authorization URL, parses the callback, and validates credentials -- usable as an embedded library.
- `wp_auth_service`, a FastAPI wrapper around that library exposing a REST API (`/api/v1/auth/url`, `/api/v1/auth/callback`, `/api/v1/auth/validate`, plus config and API-key management endpoints) with interactive docs at `/docs`, an in-memory/Redis cache, and an admin web UI at `http://localhost:8000` for configuration, API-key generation, and end-to-end auth testing.
- `belchamber-auth-bridge`, the paired WordPress plugin (`auth-service/belchamber-auth-bridge/`) that adds the session-storage layer WP core doesn't provide: a `wp_belchamber_auth_sessions` DB table, per-app global key/value storage, REST endpoints under `/wp-json/auth-bridge/v1/`, rate limiting, and an admin UI for app whitelisting and active-connection/audit visibility. It works standalone -- any HTTP client can call it directly with an Application Password, without the Python service.
- `auth_kit`, a Flutter client SDK (`auth-service/sdks/flutter/auth_kit`) with a swappable `AuthProvider` interface, a `WordPressAppPasswordProvider` (WebView redirect on mobile, loopback-server catcher on desktop/web) and a `JwtAuthProvider`, plus a self-guided in-app credential wizard UI (`AuthWizardScreen`) so consuming apps never hardcode which backend is active.

## Who it's for

Developers with a WordPress site who need login for something that is not
WordPress -- a script, a mobile app, a small internal tool -- and would rather
let WP own accounts and credential validation than build that again. Any client
that can speak HTTP Basic Auth with an Application Password can use the plugin
directly; Flutter apps can use `auth_kit`.

It is maintained by one person for their own projects, and published because
the problem is not specific to them. That is the honest scope: GPL-2.0, no
support commitment, and not a multi-tenant SaaS.

## What it is not

- Not a general-purpose OAuth/OIDC provider or identity system -- it is scoped specifically to WordPress Application Passwords as the credential mechanism.
- Not a replacement for WordPress user management -- WP core still owns accounts, roles, and password validation; this project only adds URL/callback plumbing and session storage around it.
- Not multi-site-aware yet ("multi-site WordPress support" is listed as a future direction, not current behavior).
- Not a mobile-only or Flutter-only project -- the core service and plugin are backend-agnostic; `auth_kit` is one client among planned future SDKs (PHP/Node/Angular are named as siblings, not yet built).
- Not the place to store real per-app user data beyond session/auth state -- the plugin's storage is deliberately minimal (session table + a flat global key/value store), not a general data backend.

## Related projects -- and, if applicable, how they work together

This repository is the **published** copy. Development happens in a private
upstream repo and is synced out here, so changes to the auth stack should be
made upstream rather than independently here -- an edit made only in this repo
risks being overwritten by the next sync.

Its consumers today are a Flutter app using `auth_kit` as a direct dependency,
and a second app using the plugin's REST endpoints for account login and sync
(where it appears under the plugin's former name, `wp-app-bridge`). Both are
private, so what is worth taking from that is only this: the two client paths
described above are both exercised in practice, not merely designed.
