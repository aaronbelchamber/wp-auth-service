import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:auth_kit/auth_kit.dart';

/// No-network [AuthProvider] for testing `AuthWizardScreen`/app routing
/// without a real WordPress site or JWT server. Ships with the package so
/// consuming apps' tests can depend on it too.
class FakeAuthProvider extends AuthProvider {
  bool _isLoggedIn;
  AuthIdentity? _identity;

  FakeAuthProvider({bool isLoggedIn = false}) : _isLoggedIn = isLoggedIn;

  @override
  Future<void> init() async {}

  @override
  bool get isLoggedIn => _isLoggedIn;

  @override
  AuthIdentity? get currentIdentity => _identity;

  @override
  bool get supportsSelfServicePasswordReset => false;

  @override
  Widget buildLoginContent(BuildContext context, {required VoidCallback onSuccess}) {
    return Center(
      child: ElevatedButton(
        onPressed: () {
          _isLoggedIn = true;
          _identity = const AuthIdentity(id: 'fake-user', displayName: 'Fake User', backend: AuthBackendKind.jwt);
          notifyListeners();
          onSuccess();
        },
        child: const Text('Fake Log In'),
      ),
    );
  }

  @override
  http.Client get client => MockClient((request) async => http.Response('{}', 200));

  @override
  Future<void> logout() async {
    _isLoggedIn = false;
    _identity = null;
    notifyListeners();
  }
}
