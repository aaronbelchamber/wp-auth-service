import 'package:flutter/widgets.dart';
import 'package:http/http.dart' as http;

import 'auth_identity.dart';

/// The pluggable contract between an app and whichever auth backend is
/// active — "a DBAL, but for auth". App code (routing, screens, networking)
/// should only ever depend on this interface, never on a concrete provider,
/// so swapping backends is a config change, not a code change.
///
/// [ChangeNotifier]-based so it drops straight into `GoRouter`'s
/// `refreshListenable` the way a single-backend auth service would.
abstract class AuthProvider extends ChangeNotifier {
  /// Loads any persisted credential from local storage. Must not make a
  /// network call — [isLoggedIn] needs to be answerable synchronously and
  /// cheaply immediately after this completes, so the app never has to
  /// re-validate credentials just to decide which screen to show.
  Future<void> init();

  /// Synchronous, cached — never triggers a network request. Credential
  /// revocation is detected lazily: if a request made via [client] comes
  /// back 401, the provider clears its cached state and calls
  /// [notifyListeners], rather than this getter ever polling the backend.
  bool get isLoggedIn;

  /// `null` when not logged in.
  AuthIdentity? get currentIdentity;

  /// Whether this backend has its own self-service "forgot password" flow
  /// the wizard can rely on, so calling UI can decide whether to show its
  /// own fallback messaging.
  bool get supportsSelfServicePasswordReset;

  /// Builds this backend's login step content (a WebView/browser flow, a
  /// plain form, whatever fits). Hosting chrome (app bar, wizard shell) is
  /// supplied by the caller — see `AuthWizardScreen`. Must call [onSuccess]
  /// once login completes and [isLoggedIn] is true.
  Widget buildLoginContent(BuildContext context, {required VoidCallback onSuccess});

  /// An HTTP client that injects whatever auth header this backend needs
  /// (Basic Auth for WordPress Application Passwords, Bearer for JWT) on
  /// every request. Callers should never construct their own header.
  http.Client get client;

  /// Clears local credentials, and — where the backend supports it — also
  /// revokes the credential server-side, so "log out" actually means the
  /// device can no longer authenticate, not just that this app forgot it.
  Future<void> logout();
}
