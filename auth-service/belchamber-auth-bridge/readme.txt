=== Belchamber Auth Bridge & Session Storage ===
Contributors: aaronbelchamber
Tags: authentication, rest-api, application-passwords, sessions, api
Requires at least: 5.6
Tested up to: 6.6
Requires PHP: 7.4
Stable tag: 1.3.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Turns a WordPress site into a session-storage and per-app data REST backend for other apps, on top of native Application Passwords.

== Description ==

Belchamber Auth Bridge & Session Storage provides the one piece WordPress's native Application Passwords don't: server-side session storage, so a connected app can stay authenticated without re-validating credentials on every request. It also adds per-app (non-PII) global data storage, rate-limited REST endpoints under `/wp-json/auth-bridge/v1/`, and an admin UI for managing connected applications, whitelisting, and audit logs.

Works standalone — any HTTP client can call it directly with an Application Password. Commonly paired with [wp-auth-service](https://github.com/aaronbelchamber/wp-auth-service), a Python/FastAPI service implementing the auth-URL/callback flow, but that pairing is optional.

Part of a small family of free WordPress utilities — more at [tools.belchamber.us](https://tools.belchamber.us).

== Installation ==

1. Upload the `belchamber-auth-bridge` folder to `/wp-content/plugins/`.
2. Activate through the 'Plugins' menu in WordPress.
3. Configure whitelisted apps and owners under Application Connections & Auth Service.

== Changelog ==

= 1.3.0 =
* Renamed from `wp-app-bridge` to `belchamber-auth-bridge` for clarity. Activation automatically migrates existing session/global-data/audit-log tables and option values from the old plugin, and deactivates the old plugin entry.
* REST namespace moved from `app/v1` to `auth-bridge/v1`.

== Frequently Asked Questions ==

= Do I need the Python auth-service too? =
No. This plugin's REST endpoints work with any client that can send an Application Password over HTTP Basic Auth. The Python service is a convenience wrapper, not a requirement.

= I'm upgrading from wp-app-bridge — will I lose my whitelist/sessions? =
No — activating this plugin detects the old plugin's tables and options and migrates them forward automatically.
