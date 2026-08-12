import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:auth_kit/auth_kit.dart';

import 'fake_auth_provider.dart';

void main() {
  testWidgets('AuthWizardScreen calls onSuccess and provider becomes logged in', (tester) async {
    final provider = FakeAuthProvider();
    var successCalled = false;

    await tester.pumpWidget(MaterialApp(
      home: AuthWizardScreen(
        provider: provider,
        onSuccess: () => successCalled = true,
      ),
    ));

    expect(provider.isLoggedIn, isFalse);
    expect(find.text('Fake Log In'), findsOneWidget);

    await tester.tap(find.text('Fake Log In'));
    await tester.pump();

    expect(successCalled, isTrue);
    expect(provider.isLoggedIn, isTrue);
    expect(provider.currentIdentity, isNotNull);
  });
}
