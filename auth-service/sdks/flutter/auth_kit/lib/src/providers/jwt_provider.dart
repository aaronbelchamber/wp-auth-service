import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../auth_identity.dart';
import '../auth_provider.dart';
import '../wizard/credential_form_view.dart';

/// [AuthProvider] backed by a bespoke JWT login/refresh microservice
/// (`POST {baseUrl}/login`, `POST {baseUrl}/refresh`). This is a reshape of
/// the JWT logic every consuming app already had (login + secure-storage +
/// refresh-on-expiry), proving the [AuthProvider] abstraction holds for a
/// second, unrelated backend — not just WordPress.
class JwtAuthProvider extends AuthProvider {
  final String baseUrl;
  final FlutterSecureStorage _secureStorage;

  static const _accessTokenKey = 'auth_kit_jwt_access_token';
  static const _refreshTokenKey = 'auth_kit_jwt_refresh_token';
  static const _accessTokenExpiryKey = 'auth_kit_jwt_access_token_expiry';
  static const _emailKey = 'auth_kit_jwt_email';

  String? _accessToken;
  String? _refreshToken;
  DateTime? _accessTokenExpiry;
  String? _email;

  JwtAuthProvider({
    required this.baseUrl,
    FlutterSecureStorage? secureStorage,
  }) : _secureStorage = secureStorage ?? const FlutterSecureStorage();

  @override
  Future<void> init() async {
    _accessToken = await _secureStorage.read(key: _accessTokenKey);
    _refreshToken = await _secureStorage.read(key: _refreshTokenKey);
    _email = await _secureStorage.read(key: _emailKey);
    final expiryString = await _secureStorage.read(key: _accessTokenExpiryKey);
    if (expiryString != null) {
      _accessTokenExpiry = DateTime.parse(expiryString);
    }
  }

  @override
  bool get isLoggedIn =>
      _accessToken != null && _accessTokenExpiry != null && _accessTokenExpiry!.isAfter(DateTime.now());

  @override
  AuthIdentity? get currentIdentity {
    if (!isLoggedIn || _email == null) return null;
    return AuthIdentity(id: _email!, displayName: _email!, email: _email, backend: AuthBackendKind.jwt);
  }

  @override
  bool get supportsSelfServicePasswordReset => false;

  Future<bool> login(String email, String password) async {
    final url = Uri.parse('$baseUrl/login');
    final client = http.Client();
    try {
      final response = await client.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email, 'password': password}),
      );

      if (response.statusCode != 200) return false;

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      _accessToken = data['access_token'] as String;
      _refreshToken = data['refresh_token'] as String;
      _accessTokenExpiry = DateTime.now().add(Duration(seconds: data['expires_in'] as int));
      _email = email;

      await _secureStorage.write(key: _accessTokenKey, value: _accessToken);
      await _secureStorage.write(key: _refreshTokenKey, value: _refreshToken);
      await _secureStorage.write(key: _accessTokenExpiryKey, value: _accessTokenExpiry!.toIso8601String());
      await _secureStorage.write(key: _emailKey, value: _email);

      notifyListeners();
      return true;
    } catch (e) {
      debugPrint('auth_kit JwtAuthProvider login error: $e');
      return false;
    } finally {
      client.close();
    }
  }

  Future<bool> _refreshTokenIfNeeded() async {
    if (_refreshToken == null) {
      await logout();
      return false;
    }

    final url = Uri.parse('$baseUrl/refresh');
    final client = http.Client();
    try {
      final response = await client.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': _refreshToken}),
      );

      if (response.statusCode != 200) {
        await logout();
        return false;
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      _accessToken = data['access_token'] as String;
      _accessTokenExpiry = DateTime.now().add(Duration(seconds: data['expires_in'] as int));

      await _secureStorage.write(key: _accessTokenKey, value: _accessToken);
      await _secureStorage.write(key: _accessTokenExpiryKey, value: _accessTokenExpiry!.toIso8601String());

      notifyListeners();
      return true;
    } catch (e) {
      debugPrint('auth_kit JwtAuthProvider refresh error: $e');
      return false;
    } finally {
      client.close();
    }
  }

  @override
  Widget buildLoginContent(BuildContext context, {required VoidCallback onSuccess}) {
    return CredentialFormView(
      title: 'Log In',
      userLabel: 'Email',
      onSubmit: (email, password) async {
        final success = await login(email, password);
        if (success) onSuccess();
        return success;
      },
    );
  }

  @override
  http.Client get client => _JwtClient(this);

  @override
  Future<void> logout() async {
    // Delete only this provider's own keys — never deleteAll(), which would
    // also wipe any unrelated connection sharing the same secure-storage
    // backing store (e.g. an app-owner WordPressAppPasswordProvider
    // instance running alongside this one).
    await _secureStorage.delete(key: _accessTokenKey);
    await _secureStorage.delete(key: _refreshTokenKey);
    await _secureStorage.delete(key: _accessTokenExpiryKey);
    await _secureStorage.delete(key: _emailKey);
    _accessToken = null;
    _refreshToken = null;
    _accessTokenExpiry = null;
    _email = null;
    notifyListeners();
  }
}

/// Injects the Bearer token on every request, and refreshes-then-retries
/// once on a 401 before giving up and logging out — this is what lets
/// [AuthProvider.isLoggedIn] stay a cheap, synchronous, cached getter
/// instead of something that has to hit the network to be trustworthy.
class _JwtClient extends http.BaseClient {
  final JwtAuthProvider _provider;
  final http.Client _inner = http.Client();

  _JwtClient(this._provider);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    request.headers['Authorization'] = 'Bearer ${_provider._accessToken}';
    var response = await _inner.send(request);

    if (response.statusCode == 401) {
      final refreshed = await _provider._refreshTokenIfNeeded();
      if (refreshed) {
        final retryRequest = _copyRequest(request);
        retryRequest.headers['Authorization'] = 'Bearer ${_provider._accessToken}';
        response = await _inner.send(retryRequest);
      }
    }

    return response;
  }

  http.BaseRequest _copyRequest(http.BaseRequest request) {
    if (request is http.Request) {
      final copy = http.Request(request.method, request.url)
        ..headers.addAll(request.headers)
        ..bodyBytes = request.bodyBytes;
      return copy;
    }
    return request;
  }
}
