/// Web stub — `dart:io` (and a bindable loopback socket) doesn't exist in a
/// browser at all, so the desktop OAuth-loopback pattern is fundamentally
/// not possible here. Exists purely so the app *compiles* for web; calling
/// [start] fails clearly rather than the whole app failing to build.
/// Selected via the conditional export in `loopback_auth_catcher.dart` when
/// `dart:io` isn't available.
class LoopbackAuthCatcher {
  Future<int> start() async {
    throw UnsupportedError(
      'The WordPress login wizard\'s desktop flow is not supported in a web browser build. '
      'Use the mobile (in-app WebView) build, a desktop build, or the manual '
      'Application Password entry fallback.',
    );
  }

  Future<Map<String, String>?> waitForCallback({Duration timeout = const Duration(minutes: 5)}) async => null;

  Future<void> close() async {}
}
