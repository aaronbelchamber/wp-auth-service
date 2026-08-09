# Agent Tool Configuration — Antigravity IDE

> [!NOTE]
> This file is **Antigravity IDE agent configuration**. It injects project-scoped rules into AI agent sessions.
> For human-readable contribution guidelines and the versioning policy, see [CONTRIBUTING.md](../CONTRIBUTING.md).

---

# Project Rules & Customizations

## Plugin Versioning Policy
- Whenever modifying, updating, or adding features/fixes to the WordPress plugin (`wp-app-bridge`), you MUST incrementally increase the plugin version number (patch, minor, or major as appropriate).
- Ensure version updates are synchronized across:
  1. Header constant in `wp-app-bridge.php` (`Version: X.Y.Z`)
  2. PHP Constant `WP_APP_BRIDGE_VERSION`
  3. PHP Constant `WP_APP_BRIDGE_DB_VERSION` (when DB changes occur)
  4. Option updates in activation/update hooks.
