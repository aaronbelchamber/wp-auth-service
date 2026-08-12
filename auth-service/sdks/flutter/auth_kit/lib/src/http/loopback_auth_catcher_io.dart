import 'dart:async';
import 'dart:io';

/// Real implementation, for platforms where `dart:io` (and a bindable
/// socket) is actually available — desktop and mobile, never web. Selected
/// via the conditional export in `loopback_auth_catcher.dart`.
class LoopbackAuthCatcher {
  HttpServer? _server;

  /// Starts listening and returns the port to embed in `success_url`.
  Future<int> start() async {
    _server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    return _server!.port;
  }

  /// Completes with the callback's query parameters once WordPress redirects
  /// here, or completes with `null` on [timeout] / [cancel].
  Future<Map<String, String>?> waitForCallback({Duration timeout = const Duration(minutes: 5)}) async {
    final server = _server;
    if (server == null) {
      throw StateError('LoopbackAuthCatcher.start() must be called before waitForCallback().');
    }

    try {
      final request = await server.first.timeout(timeout);
      final params = request.uri.queryParameters;

      request.response
        ..statusCode = 200
        ..headers.contentType = ContentType.html
        ..write('<html><body><p>You can close this window and return to the app.</p></body></html>');
      await request.response.close();

      return params;
    } on TimeoutException {
      return null;
    } finally {
      await close();
    }
  }

  Future<void> close() async {
    await _server?.close(force: true);
    _server = null;
  }
}
