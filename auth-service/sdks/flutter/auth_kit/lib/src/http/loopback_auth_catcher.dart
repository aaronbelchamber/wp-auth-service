/// Binds a one-shot HTTP server on `127.0.0.1` and waits for WordPress's
/// `authorize-application.php` redirect to land on it — the standard
/// desktop OAuth "loopback" pattern. No OS-level custom URL scheme or deep
/// link registration required.
///
/// Also used conceptually on mobile (see `WordPressAuthorizeView`), where a
/// WebView intercepts the same `127.0.0.1` URL shape before it's ever
/// actually dispatched, so no server needs to bind there at all.
///
/// `dart:io` (and a bindable socket) doesn't exist on web, so the real
/// implementation is only pulled in on platforms where it's actually
/// available — see `loopback_auth_catcher_io.dart` vs
/// `loopback_auth_catcher_web.dart`. This avoids the whole app failing to
/// *compile* for web just because this file exists in the dependency graph.
export 'loopback_auth_catcher_web.dart' if (dart.library.io) 'loopback_auth_catcher_io.dart';
