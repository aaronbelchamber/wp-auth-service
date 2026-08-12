# Changelog

## 0.2.0

- `WordPressAppPasswordProvider` gains `appId` (stable, whitelist-checked —
  paired with a plugin-side fix so the whitelist matches `app_id` OR
  `app_name`) and `connectionId` (namespaces secure-storage keys, so one app
  can hold multiple independent WordPress connections at once, e.g. an
  end-user login plus a separate app-owner/service connection).
- Pre-flight `GET /auth-bridge/v1/health?app_id=` check before opening the
  browser/WebView — fails open, never blocks login on a network error.
- `logout()`/401-handling on both providers now delete only their own
  storage keys instead of `deleteAll()`, so multiple connections/providers
  sharing the same on-device secure storage can't clobber each other.
- New test: two `connectionId`s don't clobber each other's stored credential.
- Requires the paired `belchamber-auth-bridge.php` v1.3.0+ for `appId`/`/global`
  support (still works against older plugin versions via the `appName`
  whitelist fallback and the pre-flight check's fail-open behavior).

## 0.1.0

- Initial release.
- `AuthProvider` interface (swappable auth backend contract).
- `WordPressAppPasswordProvider` — self-guided in-app wizard for WordPress
  Application Passwords (WebView on mobile, system-browser loopback on
  desktop/web), manual fallback entry, server-side revoke on logout.
- `JwtAuthProvider` — wraps a login/refresh JWT microservice behind the same
  interface.
- `AuthWizardScreen` — shared entry point/chrome for both.
