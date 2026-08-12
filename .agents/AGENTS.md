# Agent Tool Configuration — Antigravity IDE

> [!NOTE]
> This file is **Antigravity IDE agent configuration**. It injects project-scoped rules into AI agent sessions.
> For human-readable contribution guidelines and the versioning policy, see [CONTRIBUTING.md](../CONTRIBUTING.md).

---

# Project Rules & Customizations

## Plugin Versioning Policy
- Whenever modifying, updating, or adding features/fixes to `belchamber-auth-bridge`, you MUST incrementally increase the plugin version number (patch, minor, or major as appropriate).
- Sync across: header `Version:` in `belchamber-auth-bridge.php`, the `BELCHAMBER_AUTH_BRIDGE_VERSION` constant, `readme.txt`'s `Stable tag:`, and — only when the DB schema actually changed — `BELCHAMBER_AUTH_BRIDGE_DB_VERSION` plus its activation-hook `update_option()` call.
- Full policy: [CONTRIBUTING.md](../CONTRIBUTING.md).
