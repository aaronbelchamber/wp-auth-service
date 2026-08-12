import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../auth_identity.dart';
import '../auth_provider.dart';
import '../wizard/credential_form_view.dart';
import '../wizard/wordpress_authorize_view.dart';

/// [AuthProvider] backed by WordPress Application Passwords, via the
/// self-guided `authorize-application.php` browser/WebView flow (see
/// [WordPressAuthorizeView]) plus a manual "paste an Application Password"
/// fallback.
///
/// [appId] is the stable, whitelist-checked identity (`belchamber_auth_bridge_app_whitelist`
/// in `belchamber-auth-bridge.php`, matched against either `appId` or `appName`) — keep
/// it constant across every install of this app/role. [appName] is just the
/// human-editable label shown on the resulting Application Password; safe to
/// customize per install.
///
/// [connectionId] namespaces this instance's secure-storage keys, so a single
/// app can hold more than one independent WordPress connection at once — e.g.
/// the normal end-user login (`connectionId: 'default'`, the default) plus a
/// separate app-owner/service connection (`connectionId: 'owner'`) used only
/// on builds flagged as the app's owner. Each instance is fully independent:
/// separate credentials, separate [isLoggedIn], separate [logout].
class WordPressAppPasswordProvider extends AuthProvider {
  final String siteUrl;
  final String appId;
  final String appName;
  final String connectionId;
  final FlutterSecureStorage _secureStorage;

  static const _userLoginKeyBase = 'auth_kit_wp_user_login';
  static const _passwordKeyBase = 'auth_kit_wp_app_password';
  static const _uuidKeyBase = 'auth_kit_wp_app_password_uuid';

  String? _userLogin;
  String? _password;
  String? _uuid;

  WordPressAppPasswordProvider({
    required this.siteUrl,
    required this.appId,
    required this.appName,
    this.connectionId = 'default',
    FlutterSecureStorage? secureStorage,
  }) : _secureStorage = secureStorage ?? const FlutterSecureStorage();

  // The default connectionId keeps unprefixed keys, so credentials stored by
  // earlier auth_kit versions (before connectionId existed) still load.
  String _storageKey(String base) => connectionId == 'default' ? base : '${connectionId}_$base';

  @override
  Future<void> init() async {
    _userLogin = await _secureStorage.read(key: _storageKey(_userLoginKeyBase));
    _password = await _secureStorage.read(key: _storageKey(_passwordKeyBase));
    _uuid = await _secureStorage.read(key: _storageKey(_uuidKeyBase));
  }

  @override
  bool get isLoggedIn => _userLogin != null && _password != null;

  @override
  AuthIdentity? get currentIdentity {
    if (!isLoggedIn) return null;
    return AuthIdentity(id: _userLogin!, displayName: _userLogin!, backend: AuthBackendKind.wordpress);
  }

  @override
  bool get supportsSelfServicePasswordReset => true;

  String _basicAuthHeader(String user, String password) => 'Basic ${base64Encode(utf8.encode('$user:$password'))}';

  /// Completes login with a captured (userLogin, applicationPassword) pair —
  /// used by both the guided wizard and the manual fallback entry. Fetches
  /// and persists the credential's `uuid` via WordPress core's introspection
  /// endpoint so [logout] can later revoke it server-side (the
  /// authorize-application.php redirect itself only ever returns the
  /// username/password, never the uuid).
  Future<bool> _completeLogin(String userLogin, String password) async {
    final client = http.Client();
    try {
      final response = await client.get(
        Uri.parse('$siteUrl/wp-json/wp/v2/users/me/application-passwords/introspect'),
        headers: {'Authorization': _basicAuthHeader(userLogin, password)},
      );

      if (response.statusCode != 200) return false;

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final uuid = data['uuid'] as String?;

      _userLogin = userLogin;
      _password = password;
      _uuid = uuid;

      await _secureStorage.write(key: _storageKey(_userLoginKeyBase), value: userLogin);
      await _secureStorage.write(key: _storageKey(_passwordKeyBase), value: password);
      if (uuid != null) await _secureStorage.write(key: _storageKey(_uuidKeyBase), value: uuid);

      notifyListeners();
      return true;
    } catch (e) {
      debugPrint('auth_kit WordPressAppPasswordProvider login error: $e');
      return false;
    } finally {
      client.close();
    }
  }

  @override
  Widget buildLoginContent(BuildContext context, {required VoidCallback onSuccess}) {
    return _WordPressLoginContent(provider: this, onSuccess: onSuccess);
  }

  @override
  http.Client get client => _BasicAuthClient(this);

  @override
  Future<void> logout() async {
    if (isLoggedIn && _uuid != null) {
      final client = http.Client();
      try {
        await client.delete(
          Uri.parse('$siteUrl/wp-json/wp/v2/users/me/application-passwords/$_uuid'),
          headers: {'Authorization': _basicAuthHeader(_userLogin!, _password!)},
        );
      } catch (e) {
        // Best-effort — still clear local credentials below even if the
        // revoke call fails (offline, site unreachable, etc).
        debugPrint('auth_kit WordPressAppPasswordProvider revoke error: $e');
      } finally {
        client.close();
      }
    }

    await _clearStoredCredential();
    _userLogin = null;
    _password = null;
    _uuid = null;
    notifyListeners();
  }

  /// Clears local credentials without attempting server-side revocation —
  /// used when a request already came back 401, meaning the credential is
  /// already invalid server-side and there's nothing left to revoke.
  Future<void> _handleUnauthorized() async {
    await _clearStoredCredential();
    _userLogin = null;
    _password = null;
    _uuid = null;
    notifyListeners();
  }

  /// Deletes only this instance's own keys — never `deleteAll()`, which
  /// would also wipe out any other [connectionId]'s credentials sharing the
  /// same secure-storage backing store (e.g. the app-owner connection
  /// alongside the normal end-user one).
  Future<void> _clearStoredCredential() async {
    await _secureStorage.delete(key: _storageKey(_userLoginKeyBase));
    await _secureStorage.delete(key: _storageKey(_passwordKeyBase));
    await _secureStorage.delete(key: _storageKey(_uuidKeyBase));
  }
}

class _WordPressLoginContent extends StatefulWidget {
  final WordPressAppPasswordProvider provider;
  final VoidCallback onSuccess;

  const _WordPressLoginContent({required this.provider, required this.onSuccess});

  @override
  State<_WordPressLoginContent> createState() => _WordPressLoginContentState();
}

class _WordPressLoginContentState extends State<_WordPressLoginContent> {
  bool _manualEntry = false;

  Future<void> _handleAuthorized(String userLogin, String password) async {
    final success = await widget.provider._completeLogin(userLogin, password);
    if (success) widget.onSuccess();
  }

  @override
  Widget build(BuildContext context) {
    if (_manualEntry) {
      return CredentialFormView(
        title: 'Enter your Application Password',
        userLabel: 'WordPress Username',
        passwordLabel: 'Application Password',
        onSubmit: (user, password) async {
          final success = await widget.provider._completeLogin(user, password);
          if (success) widget.onSuccess();
          return success;
        },
        footer: TextButton(
          onPressed: () => setState(() => _manualEntry = false),
          child: const Text('Back to guided login'),
        ),
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Expanded(
          child: WordPressAuthorizeView(
            siteUrl: widget.provider.siteUrl,
            appId: widget.provider.appId,
            appName: widget.provider.appName,
            onAuthorized: _handleAuthorized,
          ),
        ),
        TextButton(
          onPressed: () => setState(() => _manualEntry = true),
          child: const Text('Advanced: enter an Application Password manually'),
        ),
      ],
    );
  }
}

/// Injects Basic Auth on every request; on a 401 (credential revoked from
/// WP Admin, expired, etc.) clears local state via [AuthProvider.logout] so
/// the app falls back to the login wizard on the next redirect check,
/// instead of silently failing requests forever.
class _BasicAuthClient extends http.BaseClient {
  final WordPressAppPasswordProvider _provider;
  final http.Client _inner = http.Client();

  _BasicAuthClient(this._provider);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    request.headers['Authorization'] =
        _provider._basicAuthHeader(_provider._userLogin ?? '', _provider._password ?? '');
    final response = await _inner.send(request);

    if (response.statusCode == 401) {
      await _provider._handleUnauthorized();
    }

    return response;
  }
}
