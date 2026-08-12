# WordPress Auth Service

> Built by [Aaron Belchamber](https://belchamber.us) — Business Growth & Cloud Systems Architect
> A standalone plug-and-play authentication service — no dependency on any other project.
> More: [Brandager.com](https://brandager.com) · [Belchamber.us](https://belchamber.us) · [Tools.Belchamber.us](https://tools.belchamber.us)

A standalone Python auth service that lets any custom application authenticate its users through a WordPress site using the native [Application Passwords](https://make.wordpress.org/core/2020/11/05/application-passwords-integration-guide/) flow (built into WordPress 5.6+), plus `belchamber-auth-bridge` — the one WordPress plugin it pairs with, which adds the session-storage layer WordPress core doesn't provide.

**Quick links:** [Auth Service README](auth-service/README.md) · [Data Security & Governance](auth-service/DATA_SECURITY_GOVERNANCE.md) · [Contributing & Versioning](CONTRIBUTING.md) · [Project Overview](docs/project-overview.md) · [Architecture & Design](auth-service/docs/architecture.md)

---

## 📦 What's Here

### [`auth-service/`](auth-service/)

The Python service (`wp_auth_lib` — zero-dependency auth library, `wp_auth_service` — FastAPI wrapper) plus [`belchamber-auth-bridge/`](auth-service/belchamber-auth-bridge/), the WordPress-side plugin it talks to. See [auth-service/README.md](auth-service/README.md) for the full setup, quickstart, and API reference — it isn't duplicated here.

`belchamber-auth-bridge` also works entirely on its own — any HTTP client can call its REST endpoints directly with a WordPress Application Password. The Python service is a convenience layer (auth-URL/callback flow, caching, a ready-made API), not a hard requirement.

---

## ⚡ Quick Start

```bash
cd auth-service
./setup.sh   # or .\setup.ps1 on Windows
```

Then install `auth-service/belchamber-auth-bridge/belchamber-auth-bridge.php` on your WordPress site's `wp-content/plugins/` directory and activate it. Full walkthrough: [auth-service/README.md](auth-service/README.md).

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for versioning policy and guidelines.

## 📄 License

This project is licensed under [GPLv2 or later](LICENSE).
