# auth_kit

Drop-in, pluggable authentication SDK for Flutter apps built against the
`wp-auth-service` backends. Ships a self-guided
in-app login wizard and a swappable `AuthProvider` interface so app code
never hardcodes which auth backend is active.

This is the Flutter "flavor" of the auth-service client SDK — see
`sdks/` for future PHP/Node/Angular siblings.

## Integration steps (copy this into any new consuming app)

1. **Add the dependency**, pinned to a tag (not a branch — see Versioning
   below):

   ```yaml
   dependencies:
     auth_kit:
       git:
         url: https://github.com/aaronbelchamber/wp-auth-service.git
         path: auth-service/sdks/flutter/auth_kit
         ref: auth-kit-v0.1.0
   ```

   While actively developing against a local checkout of both repos, use a
   `dependency_overrides:` block pointing at the local path instead of
   editing the dependency line itself:

   ```yaml
   dependency_overrides:
     auth_kit:
       path: ../../Wordpress/plugins/auth-service/sdks/flutter/auth_kit
   ```

2. **Pick a backend and construct a provider**, e.g. in your app's config/
   bootstrap:

   ```dart
   final authProvider = AppConfig.authBackend == 'wordpress'
       ? WordPressAppPasswordProvider(
           siteUrl: AppConfig.wpSiteUrl,
           appId: AppConfig.wpAppId,     // stable — must be whitelisted, see below
           appName: AppConfig.wpAppName, // human label only, safe to vary per install
         )
       : JwtAuthProvider(baseUrl: AppConfig.jwtBaseUrl);

   await authProvider.init();
   ```

3. **Wire it into routing** — `AuthProvider` is a `ChangeNotifier`, so it
   drops straight into `GoRouter`:

   ```dart
   GoRouter(
     refreshListenable: authProvider,
     redirect: (context, state) => authProvider.isLoggedIn ? null : '/login',
     routes: [
       GoRoute(
         path: '/login',
         builder: (context, state) => AuthWizardScreen(
           provider: authProvider,
           onSuccess: () => context.go('/menu'),
         ),
       ),
       // ...
     ],
   )
   ```

4. **Use `authProvider.client` for authenticated requests** — it injects
   whichever header the active backend needs. Never build the header
   yourself.

5. **Log out** with `await authProvider.logout()` — for the WordPress
   backend this also revokes the Application Password server-side, not just
   locally.

## Why WordPress Application Passwords need a wizard at all

WordPress core has no JSON email+password login endpoint. The only
credential mechanism is Application Passwords, normally created by an admin
in wp-admin or via the `authorize-application.php` browser redirect.
`WordPressAppPasswordProvider` drives that redirect for you — WebView
intercept on mobile, system-browser-plus-loopback-server on desktop/web —
so end users never have to touch wp-admin themselves. See
`lib/src/wizard/wordpress_authorize_view.dart` for the mechanics.

**`appId` must exactly match an entry in the site's `belchamber_auth_bridge_app_whitelist`
setting** (WP Admin → Tools → App Connections → Settings) — keep it a single
stable value shared by every install of a given app/role (e.g.
`fun-activities-app`). `appName` is just the editable label shown on the
resulting Application Password — free to vary per install/device. (For
backward compatibility the plugin also still matches on `appName`, but
`appId` is the one to rely on going forward — see
`../../../docs/admin-auth-guide.md`.)

Before opening the browser/WebView, `WordPressAppPasswordProvider` pre-flight
checks `GET /auth-bridge/v1/health?app_id=` and shows a clear "ask your admin to
whitelist this app" message instead of attempting the redirect if it isn't —
this fails open (never blocks login) if the check itself can't complete, e.g.
offline, or an older plugin version that doesn't report whitelist status yet.

### Two connections in one app: the app-owner pattern

An app can hold more than one independent WordPress connection at once by
giving each `WordPressAppPasswordProvider` instance its own `connectionId`
(default `'default'`) — this namespaces its secure-storage keys so multiple
instances sharing the same on-device secure storage never clobber each
other's credentials, including on `logout()`. The intended use: a normal
end-user login (`connectionId: 'default'`) plus a separate "app owner" or
service connection used to authenticate *the app itself* — e.g. for writing
to `/auth-bridge/v1/global` (see the admin guide) — typically gated behind a
build-time flag so ordinary end-user builds never construct the owner
instance at all:

```dart
final ownerConnection = WordPressAppPasswordProvider(
  siteUrl: AppConfig.wpSiteUrl,
  appId: '${AppConfig.wpAppId}-owner',
  appName: 'App Owner Connection',
  connectionId: 'owner',
);
```

The `-owner` suffix just keeps the two connections distinguishable and
independently revocable in WP Admin's "Active Connections" table — it has no
bearing on who's allowed to write global data (that's a separate WP-user ACL,
see the admin guide).

## Adding a new backend

Implement `AuthProvider` (see `lib/src/auth_provider.dart`) — nothing else
in this package or in consuming apps needs to change, since `AuthWizardScreen`
and app networking code only ever depend on the interface.

## Versioning

Cut a `git tag` (e.g. `auth-kit-v0.1.1`) after any change and have
consuming apps' `ref:` point at tags, not `main` — otherwise a change made
for one app can silently break another app pinned to the same branch.

## Testing

`test/fake_auth_provider.dart` provides a no-network `FakeAuthProvider` for
testing `AuthWizardScreen`/routing in consuming apps without a real
WordPress site or JWT server.

## Further reading

- [`../../../docs/admin-auth-guide.md`](../../../docs/admin-auth-guide.md) —
  plugin setup, whitelisting, the app-owner connection, `/global` data, rate
  limits. Also written to double as an agent-actionable reference.
- [`../../../docs/user-auth-guide.md`](../../../docs/user-auth-guide.md) —
  what end users see and what to do if something goes wrong.
