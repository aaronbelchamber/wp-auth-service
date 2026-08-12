import 'package:flutter/material.dart';

/// A plain username/password form, reused by [JwtAuthProvider] as its
/// primary login step and by [WordPressAppPasswordProvider] as the manual
/// "paste an Application Password" fallback.
class CredentialFormView extends StatefulWidget {
  final String title;
  final String userLabel;
  final String passwordLabel;
  final String submitLabel;
  final bool obscurePassword;
  final FormFieldValidator<String>? userValidator;
  final FormFieldValidator<String>? passwordValidator;

  /// Returns `true` on success. On failure, return `false` and the view
  /// shows a generic error — callers wanting a specific message should
  /// surface it themselves (e.g. via a SnackBar) before returning.
  final Future<bool> Function(String user, String password) onSubmit;

  final Widget? footer;

  const CredentialFormView({
    super.key,
    required this.title,
    required this.userLabel,
    required this.onSubmit,
    this.passwordLabel = 'Password',
    this.submitLabel = 'Log In',
    this.obscurePassword = true,
    this.userValidator,
    this.passwordValidator,
    this.footer,
  });

  @override
  State<CredentialFormView> createState() => _CredentialFormViewState();
}

class _CredentialFormViewState extends State<CredentialFormView> {
  final _formKey = GlobalKey<FormState>();
  final _userController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  String? _error;

  @override
  void dispose() {
    _userController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final success = await widget.onSubmit(_userController.text, _passwordController.text);

    if (!mounted) return;
    setState(() {
      _isLoading = false;
      if (!success) _error = 'Login failed. Check your details and try again.';
    });
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 24),
            TextFormField(
              controller: _userController,
              decoration: InputDecoration(
                labelText: widget.userLabel,
                border: const OutlineInputBorder(),
              ),
              validator: widget.userValidator,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _passwordController,
              decoration: InputDecoration(
                labelText: widget.passwordLabel,
                border: const OutlineInputBorder(),
              ),
              obscureText: widget.obscurePassword,
              validator: widget.passwordValidator,
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: 32),
            _isLoading
                ? const CircularProgressIndicator()
                : ElevatedButton(
                    onPressed: _handleSubmit,
                    style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(50)),
                    child: Text(widget.submitLabel),
                  ),
            if (widget.footer != null) ...[
              const SizedBox(height: 16),
              widget.footer!,
            ],
          ],
        ),
      ),
    );
  }
}
