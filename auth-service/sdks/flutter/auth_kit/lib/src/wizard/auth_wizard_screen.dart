import 'package:flutter/material.dart';

import '../auth_provider.dart';

/// The single entry point apps call into for login, regardless of which
/// [AuthProvider] is active. Supplies consistent chrome; the provider
/// supplies the actual step content (WebView/browser flow for WordPress, a
/// plain form for JWT, etc.) via [AuthProvider.buildLoginContent].
class AuthWizardScreen extends StatelessWidget {
  final AuthProvider provider;
  final VoidCallback onSuccess;
  final String title;

  const AuthWizardScreen({
    super.key,
    required this.provider,
    required this.onSuccess,
    this.title = 'Log In',
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: provider.buildLoginContent(context, onSuccess: onSuccess),
    );
  }
}
