import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart'
    show kIsWeb, debugPrint, defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../http/loopback_auth_catcher.dart';

/// Drives WordPress's native `authorize-application.php` redirect flow and
/// hands back the resulting `user_login`/`password` on success.
///
/// Both platforms target the *same* `success_url` shape — a loopback URL
/// (`http://127.0.0.1:{port}/callback`) — because WordPress core rejects
/// non-HTTPS redirect targets by default, and `belchamber-auth-bridge.php` only
/// special-cases loopback hosts (`handle_loopback_and_whitelist_errors`).
/// A made-up custom domain would not get redirected to at all.
///
/// - Mobile: an in-app WebView intercepts the navigation attempt to that URL
///   before it dispatches — no server needs to actually listen.
/// - Desktop/web: a real loopback HTTP server catches the one redirect from
///   the system browser (the standard desktop OAuth loopback pattern).
class WordPressAuthorizeView extends StatefulWidget {
  final String siteUrl;
  final String appId;
  final String appName;

  /// Called with (userLogin, applicationPassword) on success.
  final void Function(String userLogin, String password) onAuthorized;

  const WordPressAuthorizeView({
    super.key,
    required this.siteUrl,
    required this.appId,
    required this.appName,
    required this.onAuthorized,
  });

  @override
  State<WordPressAuthorizeView> createState() => _WordPressAuthorizeViewState();
}

enum _PreflightStatus { checking, ok, notWhitelisted }

class _WordPressAuthorizeViewState extends State<WordPressAuthorizeView> {
  static const _timeout = Duration(minutes: 5);

  late final String _state;
  String? _error;
  bool _waiting = false;
  _PreflightStatus _preflight = _PreflightStatus.checking;

  // Uses defaultTargetPlatform (from package:flutter/foundation.dart) rather
  // than dart:io's Platform, which doesn't exist on web — this check itself
  // must stay web-safe even though it always evaluates false there.
  bool get _useWebView =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android || defaultTargetPlatform == TargetPlatform.iOS);

  @override
  void initState() {
    super.initState();
    _state = _randomState();
    _runPreflightCheck();
  }

  /// Checks `/auth-bridge/v1/health?app_id=` before starting the redirect flow, so an
  /// unwhitelisted app fails with a clear in-app message instead of a
  /// confusing WordPress-side error page after the browser/WebView opens.
  /// Fails open: a network error, offline check, or an older plugin version
  /// that doesn't report `app_id_whitelisted` at all never blocks login —
  /// this is a UX improvement, not a security boundary (the real boundary is
  /// still enforced server-side either way).
  Future<void> _runPreflightCheck() async {
    final client = http.Client();
    try {
      final uri = Uri.parse('${widget.siteUrl}/wp-json/auth-bridge/v1/health')
          .replace(queryParameters: {'app_id': widget.appId});
      final response = await client.get(uri).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (data.containsKey('app_id_whitelisted') && data['app_id_whitelisted'] == false) {
          if (mounted) setState(() => _preflight = _PreflightStatus.notWhitelisted);
          return;
        }
      }
    } catch (e) {
      debugPrint('auth_kit WordPressAuthorizeView preflight check error: $e');
    } finally {
      client.close();
    }

    if (mounted) setState(() => _preflight = _PreflightStatus.ok);
  }

  String _randomState() {
    final rand = Random.secure();
    return List.generate(16, (_) => rand.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }

  Uri _buildAuthorizeUri(String successUrl) {
    return Uri.parse('${widget.siteUrl}/wp-admin/authorize-application.php').replace(queryParameters: {
      'app_id': widget.appId,
      'app_name': widget.appName,
      'success_url': '$successUrl?state=$_state',
      'reject_url': '$successUrl?rejected=1&state=$_state',
    });
  }

  bool _validState(Map<String, String> params) => params['state'] == _state;

  Future<void> _startDesktopFlow() async {
    setState(() {
      _waiting = true;
      _error = null;
    });

    final catcher = LoopbackAuthCatcher();
    try {
      int port;
      try {
        port = await catcher.start();
      } on UnsupportedError catch (e) {
        setState(() {
          _waiting = false;
          _error = e.message ?? 'This login method is not supported on this platform.';
        });
        return;
      }
      final authorizeUri = _buildAuthorizeUri('http://127.0.0.1:$port/callback');

      final launched = await launchUrl(authorizeUri, mode: LaunchMode.externalApplication);
      if (!launched) {
        setState(() {
          _waiting = false;
          _error = 'Could not open your browser. Please try again.';
        });
        return;
      }

      final params = await catcher.waitForCallback(timeout: _timeout);
      if (!mounted) return;

      if (params == null) {
        setState(() {
          _waiting = false;
          _error = 'Timed out waiting for approval. Please try again.';
        });
        return;
      }

      if (params.containsKey('rejected') || !_validState(params)) {
        setState(() {
          _waiting = false;
          _error = params.containsKey('rejected')
              ? 'Authorization was declined.'
              : 'Could not verify the response — please try again.';
        });
        return;
      }

      final userLogin = params['user_login'];
      final password = params['password'];
      if (userLogin == null || password == null) {
        setState(() {
          _waiting = false;
          _error = 'WordPress did not return a valid credential.';
        });
        return;
      }

      widget.onAuthorized(userLogin, password);
    } finally {
      await catcher.close();
    }
  }

  void _cancelDesktopFlow() {
    setState(() {
      _waiting = false;
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_preflight == _PreflightStatus.checking) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_preflight == _PreflightStatus.notWhitelisted) {
      return Padding(
        padding: const EdgeInsets.all(24.0),
        child: Center(
          child: Text(
            "This app isn't approved on this WordPress site yet — ask your admin to "
            'whitelist it in Tools → App Connections → Settings.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    if (_useWebView) {
      return _MobileAuthorizeWebView(
        authorizeUri: _buildAuthorizeUri('http://127.0.0.1:0/callback'),
        matchesInterceptHost: (uri) => uri.host == '127.0.0.1',
        onIntercepted: (uri) {
          final params = uri.queryParameters;
          if (params.containsKey('rejected') || !_validState(params)) return;
          final userLogin = params['user_login'];
          final password = params['password'];
          if (userLogin != null && password != null) {
            widget.onAuthorized(userLogin, password);
          }
        },
      );
    }

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'We\'ll open your browser so you can log in to WordPress and approve this app.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          if (_waiting) ...[
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            const Text('Waiting for you to approve in your browser…'),
            const SizedBox(height: 16),
            TextButton(onPressed: _cancelDesktopFlow, child: const Text('Cancel')),
          ] else ...[
            if (_error != null) ...[
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              const SizedBox(height: 16),
            ],
            ElevatedButton(onPressed: _startDesktopFlow, child: const Text('Continue with WordPress')),
          ],
        ],
      ),
    );
  }
}

class _MobileAuthorizeWebView extends StatefulWidget {
  final Uri authorizeUri;
  final bool Function(Uri uri) matchesInterceptHost;
  final void Function(Uri uri) onIntercepted;

  const _MobileAuthorizeWebView({
    required this.authorizeUri,
    required this.matchesInterceptHost,
    required this.onIntercepted,
  });

  @override
  State<_MobileAuthorizeWebView> createState() => _MobileAuthorizeWebViewState();
}

class _MobileAuthorizeWebViewState extends State<_MobileAuthorizeWebView> {
  late final WebViewController _controller;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onNavigationRequest: (request) {
            final uri = Uri.tryParse(request.url);
            if (uri != null && widget.matchesInterceptHost(uri)) {
              widget.onIntercepted(uri);
              return NavigationDecision.prevent;
            }
            return NavigationDecision.navigate;
          },
        ),
      )
      ..loadRequest(widget.authorizeUri);
  }

  @override
  Widget build(BuildContext context) => WebViewWidget(controller: _controller);
}
