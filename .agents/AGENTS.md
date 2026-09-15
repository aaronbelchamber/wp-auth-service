> **This is Antigravity's workspace customisations root.** Two things are not
> in this file and both outrank it:
>
> - The repo's canonical rulebook is [`../AGENTS.md`](../AGENTS.md) -- the
>   architecture map, the commands, the traps. Antigravity loads that one too:
>   it globs `**/AGENTS.md`, which is also why this file is not inert. Read it,
>   and where the two disagree the root file wins.
> - Standing preferences for the whole drive are the files in
>   `E:\project-hub\docs\standards\` -- list `*.md` there and read what is
>   present rather than trusting a list here. All are canonical -- where any of
>   them and anything below disagree, they win and the text below is what to fix.
>   `gh repo clone aaronbelchamber/project-hub` if that path does not resolve.
>
> What belongs here is only what is genuinely Antigravity-specific, or an
> invariant important enough to be worth stating twice.

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
