# Deployment & Operations Guide

This guide covers deploying `belchamber-auth-bridge` plugin updates directly to remote WordPress sites using `deploy_plugin.py` and running `wp_auth_service` in cloud environments using Docker.

---

## ⚡ One-Liner Remote Plugin Deployment (`deploy_plugin.py`)

Deploy updates to the `belchamber-auth-bridge` WordPress plugin with a single command to any connected WordPress site (such as `tools.belchamber.us`). The deployer integrates seamlessly with `site-manager` config (`sites.yaml` & encrypted credentials):

```bash
# 1. Deploy live update to tools.belchamber.us (auto-commits to GitHub & uploads via SFTP)
python deploy_plugin.py --site tools-belchamber-us

# 2. Dry-run mode to verify connection & files without modifying server:
python deploy_plugin.py --site tools-belchamber-us --dry-run
```

### What `deploy_plugin.py` Does Automatically:
1. **GitHub Cloud Backup**: Stages, commits, and pushes plugin updates to `https://github.com/aaronbelchamber/wp-auth-service`.
2. **Site-Manager Integration**: Reads target site SSH details and decrypts credentials directly from `site-manager` (`sites.yaml` & `~/.wp_site_manager/credentials.enc`).
3. **SFTP Direct Upload**: Uploads plugin files via Paramiko SFTP straight to `/wp-content/plugins/belchamber-auth-bridge` on the target server.

---

## 🐳 Docker Cloud Deployment

Docker deployment is recommended for production cloud environments (AWS ECS, Google Cloud Run, Azure Container Instances) or container orchestration setups.

### Option 1: Docker Compose (Recommended)

1. **Navigate to deployment directory:**
   ```bash
   cd deployment
   ```

2. **Configure environment variables:**
   Create `.env`:
   ```bash
   WP_ROOT_URL=https://your-wordpress-site.com
   APP_NAME=Your Application
   CALLBACK_URL=https://your-app.com/callback
   CACHE_TTL=300
   CORS_ORIGINS=https://your-app.com
   LOG_LEVEL=INFO
   ```

3. **Start services:**
   ```bash
   docker-compose up -d
   ```

---

### Option 2: Single Docker Container

```bash
cd deployment
docker build -t wp-auth-service .

docker run -d \
  -p 8000:8000 \
  -e WP_ROOT_URL=https://example.com \
  -e APP_NAME="My App" \
  -e CALLBACK_URL=https://myapp.com/callback \
  wp-auth-service
```
