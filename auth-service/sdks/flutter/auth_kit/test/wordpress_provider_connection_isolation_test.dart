import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:auth_kit/auth_kit.dart';

/// In-memory stand-in for [FlutterSecureStorage] — avoids needing real
/// platform channels in a plain `flutter test` run. Shared across multiple
/// [WordPressAppPasswordProvider] instances in a test to mimic them all
/// hitting the same real secure-storage backing store on-device.
class _FakeSecureStorage extends FlutterSecureStorage {
  final Map<String, String> _store = {};

  _FakeSecureStorage();

  @override
  Future<void> write({
    required String key,
    required String? value,
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    if (value == null) {
      _store.remove(key);
    } else {
      _store[key] = value;
    }
  }

  @override
  Future<String?> read({
    required String key,
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async =>
      _store[key];

  @override
  Future<void> delete({
    required String key,
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    _store.remove(key);
  }
}

void main() {
  test('two WordPressAppPasswordProvider connectionIds do not clobber each other', () async {
    final sharedStorage = _FakeSecureStorage();

    final endUser = WordPressAppPasswordProvider(
      siteUrl: 'https://example.test',
      appId: 'fun-activities-app',
      appName: 'Fun Activities App',
      secureStorage: sharedStorage,
    );
    final owner = WordPressAppPasswordProvider(
      siteUrl: 'https://example.test',
      appId: 'fun-activities-app-owner',
      appName: 'App Owner Connection',
      connectionId: 'owner',
      secureStorage: sharedStorage,
    );

    // Directly seed the underlying store the way _completeLogin would, using
    // each instance's own key-namespacing — exercised indirectly via init()
    // reading back what was written, since _completeLogin itself makes a
    // real HTTP call.
    await sharedStorage.write(key: 'auth_kit_wp_user_login', value: 'alice');
    await sharedStorage.write(key: 'auth_kit_wp_app_password', value: 'end-user-secret');
    await sharedStorage.write(key: 'owner_auth_kit_wp_user_login', value: 'service-account');
    await sharedStorage.write(key: 'owner_auth_kit_wp_app_password', value: 'owner-secret');

    await endUser.init();
    await owner.init();

    expect(endUser.isLoggedIn, isTrue);
    expect(endUser.currentIdentity!.id, 'alice');
    expect(owner.isLoggedIn, isTrue);
    expect(owner.currentIdentity!.id, 'service-account');

    // Logging out of the owner connection must not touch the end-user one.
    await owner.logout();

    expect(owner.isLoggedIn, isFalse);
    expect(endUser.isLoggedIn, isTrue, reason: 'owner.logout() must not clear the end-user connection\'s stored credential');

    // Re-read from scratch to confirm the underlying store itself, not just
    // in-memory state, kept the end-user credential intact.
    final endUserReload = WordPressAppPasswordProvider(
      siteUrl: 'https://example.test',
      appId: 'fun-activities-app',
      appName: 'Fun Activities App',
      secureStorage: sharedStorage,
    );
    await endUserReload.init();
    expect(endUserReload.isLoggedIn, isTrue);
    expect(endUserReload.currentIdentity!.id, 'alice');
  });
}
