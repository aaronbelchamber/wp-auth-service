/// Which backend produced an [AuthIdentity]/credential.
enum AuthBackendKind { wordpress, jwt }

/// A backend-agnostic view of "who is logged in", regardless of whether the
/// active [AuthProvider] is talking to WordPress Application Passwords or a
/// JWT service.
class AuthIdentity {
  final String id;
  final String displayName;
  final String? email;
  final AuthBackendKind backend;

  const AuthIdentity({
    required this.id,
    required this.displayName,
    required this.backend,
    this.email,
  });
}
