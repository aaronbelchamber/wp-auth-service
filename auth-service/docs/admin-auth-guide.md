# Admin Auth Guide — belchamber-auth-bridge + auth_kit

For the person setting up a WordPress site to back a new app, and for coding
agents implementing that setup. Endpoint/param names below are literal —
act on them directly rather than re-deriving from `belchamber-auth-bridge.php` source.

## TL;DR

| Step | What |
|---|---|
| 1 | Install & activate `belchamber-auth-bridge.php` on the WordPress site |
| 2 | Pick a stable `app_id` for the app (e.g. `fun-activities-app`) and add it to the whitelist |
| 3 | Create a dedicated low-privilege WordPress user as the app's service account, if using the owner connection |
| 4 | (Optional) If the app needs `/global` writes, add that service account's user ID to the owners list for the app's `app_id` |
| 5 | Give the app's build config the site URL + `app_id` — end users self-serve login via the in-app wizard, nothing manual per-user |

## 1. Install the plugin

Copy `belchamber-auth-bridge/belchamber-auth-bridge.php` into the site's `wp-content/plugins/`
directory (or use `deploy_plugin.py --site <name>`, see the repo root
`README.md`) and activate it in WP Admin → Plugins. This provisions two
tables (`wp_belchamber_auth_sessions`, `wp_belchamber_auth_global_data`) and one audit-log table
(`wp_belchamber_auth_logs`) automatically.

If you're updating an already-active install in place (not
deactivate/reactivate), the plugin re-checks its DB version on the next
`wp-admin` page load and upgrades automatically — no manual step needed.

## 2. Whitelist the app

Go to **WP Admin → Tools → App Connections → Settings**. Under **Allowed
Applications Whitelist**, add the app's `app_id` (e.g. `fun-activities-app`)
— comma-separated if you're whitelisting more than one app on this site.

- Prefer `app_id` (stable, meant to never change) over `app_name` (just a
  display label, editable by whoever's authorizing). The plugin matches
  either, so existing name-based whitelist entries keep working, but new
  apps should be identified by `app_id`.
- Leaving this field blank allows *any* app to connect — fine for a
  single-admin personal site, not recommended once other people can reach
  the site's login page.
- You can check whether a given `app_id` is currently whitelisted without
  going through the full login flow: `GET {site}/wp-json/auth-bridge/v1/health?app_id=X`
  returns `{"app_id_whitelisted": true|false, ...}`. This is the same check
  the app's login wizard runs before it ever opens a browser/WebView.

## 3. End users: nothing for you to do here

Individual end users never need a wp-admin visit. Each app ships a
self-guided in-app wizard (`auth_kit`'s `AuthWizardScreen` +
`WordPressAppPasswordProvider`) that drives WordPress's native
`authorize-application.php` redirect for them — WebView on mobile,
system-browser + a local loopback listener on desktop — and captures the
resulting Application Password automatically. They just need their normal
WordPress username/password, once, the first time they open the app. See
`user-auth-guide.md` for what this looks like from their side.

They *do* need an existing WordPress account — this plugin doesn't add
self-service account registration. Create accounts the normal WordPress way
(WP Admin → Users → Add New) ahead of time.

## 4. The app-owner connection (optional — only if the app needs `/global` data)

Some apps need to share data that isn't tied to any one person — a shared
leaderboard snapshot, feature flags, an announcement. That's what
`/auth-bridge/v1/global` is for (see §6). Writing to it requires a connection that
represents *the app itself*, not any individual end user — the "app owner"
or service connection.

**Recommended: create a dedicated low-privilege WordPress user for this**,
not a personal admin account. Something like `fun-activities-app-service`
with just enough capability to be a normal author/subscriber — an
Application Password tied to this account, if it ever leaks (e.g. extracted
from a distributed app binary, since the owner connection typically runs
once from whoever administers the app's content, not from every device),
can't do more than write that one app's global data.

To connect it: build the app with its owner-connection flag enabled (see the
app's own config — e.g. `fun_activities_app` uses `IS_APP_OWNER_BUILD=true`)
and run it once, logged in as the service account, through the same wizard
end users go through. The resulting connection is stored locally on that one
device/session — it does not need to be distributed to every end-user
device, because end-user devices only ever need read access to `/global`
(public, no credential required — see §6).

Monitor/revoke it the same way as any other connection: **Tools → App
Connections → Active Connections**. It'll show up with whatever `app_name`
label the app sent (e.g. "App Owner Connection") and a distinguishable
`app_id` (convention: `{app_id}-owner`) if you whitelisted that separately —
this is purely for your own ability to tell it apart from end-user
connections and revoke it independently; it has no bearing on write
permissions (see §6).

## 5. Rate limits

`/auth-bridge/v1/session` and `/auth-bridge/v1/global` are all rate-limited per
`(user or IP, app_id, route)` using a simple fixed-window counter (WP
transients) — generous defaults (~1 req/sec sustained, small burst), meant
as a backstop against a misbehaving client, not a tight budget. Exceeding it
returns HTTP 429 with a `Retry-After` header. There's currently no admin UI
to tune these — the constants live inline in `belchamber-auth-bridge.php`'s
`get_session`/`save_session`/`delete_session`/`get_global`/`save_global`
methods (search for `check_rate_limit`) if they ever need adjusting.

Caveat: on a site without a persistent object cache (Redis/Memcached),
transients hit the `wp_options` table, adding ~2 extra DB queries per
rate-limited request — a non-issue at personal/small-app scale.

## 6. `/auth-bridge/v1/global` — app-scoped, non-PII data

| Route | Method | Auth | Notes |
|---|---|---|---|
| `/global?app_id=&key=` | GET | **None** | Public — anyone who knows/guesses `key` can read it. Only put data here that's safe to be fully public. |
| `/global` | POST (create/update), DELETE | Required + owner | Also requires the authenticated WP user be listed as an owner of `app_id` (see below) |

This is a **separate resource from `/auth-bridge/v1/session`**, which is completely
unchanged and still fully private/per-user. `/global` never reads or exposes
any user's session data — an anonymous caller can only ever see the
app-owner-authored global blob for one `app_id`.

**Configuring who's allowed to write:** same Settings tab, **Global App Data
Owners** field — one line per app, format `app_id = user_id[,user_id...]`,
e.g.:

```
fun-activities-app = 7
```

where `7` is the WordPress user ID of the dedicated service account from §4
(find a user's ID under WP Admin → Users → hover their name → the `user_id=`
in the edit-link URL). This check is purely by WordPress user ID — it does
**not** matter which `app_id`/Application Password the request happened to
authenticate with, only whether that WP user is listed here for the `app_id`
the data belongs to.

## 7. Monitoring & incident response

- **Tools → App Connections → Active Connections**: every live Application
  Password across every user, with last-used time/IP and a per-connection
  "Clear Sessions" / "Revoke" action.
- **Tools → App Connections → Audit Logs**: creation/revocation/access events.
- **Emergency Revoke All Connections** (top of the Active Connections tab):
  revokes every Application Password site-wide — use if you suspect a
  broader compromise, not for routine single-device revocation (use the
  per-row Revoke button for that).
