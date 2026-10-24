# WordPress Auth Service Documentation Hub

Welcome to the technical documentation for the WordPress Auth Service & `belchamber-auth-bridge` plugin repository.

---

## 📚 Document Directory

### 🏛️ Architecture & Design
- **[`architecture.md`](architecture.md)** — Comprehensive architecture overview, component boundaries (`wp_auth_lib`, `wp_auth_service`, `belchamber-auth-bridge`, `static`), REST API specifications, exception hierarchy, and auth sequence data flows.

### 🚀 Deployment & Operations
- **[`deployment.md`](deployment.md)** — One-liner site deployment tool (`deploy_plugin.py`) integrating with `site-manager`, SFTP live sync, and Docker / Docker Compose cloud hosting guides.

### 📜 Implementation History
- **[`implementation-log.md`](implementation-log.md)** — Phased build history, milestone completion notes, and design evolution log.

### 🤖 AI Agent Guidelines
- **[`../AGENTS.md`](../AGENTS.md)** — Agent reference sheet, system rules, OOP constraints, and command shortcuts for AI IDE agents.

---

## ⚡ Quick Reference Commands

```powershell
# Run Unit & Integration Tests
python -m pytest tests/

# Deploy Plugin Update to Live Site (e.g., tools.belchamber.us)
python deploy_plugin.py --site tools-belchamber-us

# Start Local Auth Service Server
python -m wp_auth_service.main
```
