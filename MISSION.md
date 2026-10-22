# Mission

**Retired.** No site on the drive runs WordPress, nothing consumes this repository, and the
drive's auth server is auth-service-v1. What follows describes what the
code still does, not a project in development.

wp-auth-service is a standalone authentication provider that lets any custom app -- Python, JS, mobile, CLI -- authenticate its users through a WordPress site, using WordPress's own native Application Passwords (built into WP 5.6+) instead of a hand-rolled login system. It solves one problem: don't build and maintain auth from scratch for every new app when a WordPress site can already do credential validation. It is for anyone running a WordPress site who is building apps beside it and would rather not own an auth stack per app.

## What this is for

- A Python auth core (`wp_auth_lib`, zero external dependencies) that generates the WP authorization URL, parses the callback, and validates credentials -- usable as an embedded library.
- `wp_auth_service`, a FastAPI wrapper around that library exposing a REST API (`/api/v1/auth/url`, `/api/v1/auth/callback`, `/api/v1/auth/validate`, plus config and API-key management endpoints) with interactive docs at `/docs`, an in-memory/Redis cache, and an admin web UI at `http://localhost:8000` for configuration, API-key generation, and end-to-end auth testing.
- `belchamber-auth-bridge`, the paired WordPress plugin (`auth-service/belchamber-auth-bridge/`) that adds the session-storage layer WP core doesn't provide: a `wp_belchamber_auth_sessions` DB table, per-app global key/value storage, REST endpoints under `/wp-json/auth-bridge/v1/`, rate limiting, and an admin UI for app whitelisting and active-connection/audit visibility. It works standalone -- any HTTP client can call it directly with an Application Password, without the Python service.

## Who it's for

Developers with a WordPress site who need login for something that is not
WordPress -- a script, a mobile app, a small internal tool -- and would rather
let WP own accounts and credential validation than build that again. Any client
that can speak HTTP Basic Auth with an Application Password can use the plugin
directly. Flutter apps use the `auth_kit` SDK, which lives in auth-service-v1.

It is maintained by one person for their own projects, and published because
the problem is not specific to them. That is the honest scope: GPL-2.0, no
support commitment, and not a multi-tenant SaaS.

## What it is not

- Not a general-purpose OAuth/OIDC provider or identity system -- it is scoped specifically to WordPress Application Passwords as the credential mechanism.
- Not a replacement for WordPress user management -- WP core still owns accounts, roles, and password validation; this project only adds URL/callback plumbing and session storage around it.
- Not multi-site-aware yet ("multi-site WordPress support" is listed as a future direction, not current behavior).
- Not a mobile-only or Flutter-only project -- the core service and plugin are backend-agnostic; this repository ships no client SDK (`auth_kit` is in auth-service-v1).
- Not the place to store real per-app user data beyond session/auth state -- the plugin's storage is deliberately minimal (session table + a flat global key/value store), not a general data backend.

## Interfaces

```yaml
project_kind: app
provides:
  - name: auth-bridge-rest-api
    surface: "/wp-json/auth-bridge/v1/* -- belchamber-auth-bridge plugin, session storage, rate limiting, app whitelisting; any HTTP client with a WP Application Password can call it directly"
    kind: http
    stable: true
    consumers: []
    note: "No consumer: where-am-i-app signs in through auth-service-v1 (since 09/23/2026) and fun-activities-app-flutter keeps its WordPress backend dormant with no server behind it; neither calls these endpoints. None of Aaron's sites runs WordPress, so nothing serves this route today."
  - name: wp-auth-service-api
    surface: "http://localhost:8000 -- FastAPI wrapper (/api/v1/auth/url, /callback, /validate), admin UI + interactive docs at /docs"
    kind: http
    stable: true
    consumers: []
    note: "Not in the portfolio's 62000-62099/63000-63099 port band -- deliberately outside it, not portfolio-supervised."
consumes: []
```

## Related projects -- and, if applicable, how they work together

This repository is a public copy of `auth-service/` in the private repository
`belchamber-plugins-private`, kept in step by hand. It has its own git history
and no automated sync: `auth-service/check_sync.py`, run by hand, compares
`deploy_plugin.py` and `_credentials.py` with the private copy. The two differ:
`belchamber-auth-bridge` is 1.3.0 here and 1.4.0 there. Changes to the auth
stack are made in the private repository first; an edit made only here can be
overwritten when the next hand-sync copies files over. It has no runtime
dependency on any other project.

Neither fun-activities-app-flutter nor where-am-i-app calls the plugin's REST
endpoints (see the `auth-bridge-rest-api` note above). The `auth_kit` Flutter SDK
no longer has a copy here: it lives in `auth-service-v1` at `sdks/flutter/auth_kit`,
which is what both apps depend on.
