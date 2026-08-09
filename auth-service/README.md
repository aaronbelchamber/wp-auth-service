# WordPress Auth Service

A standalone authentication service that lets your application authenticate users with WordPress sites using the WordPress Application Passwords flow. Use it as a Python library in your app, or run it as a standalone service.


## WordPress Prerequisites & Requirements

> [!NOTE]
> **Authentication** uses WordPress's native Application Passwords (built into WP 5.6+) — no plugin needed for auth alone.
> **Session & state storage** (`/wp-json/app/v1/`) requires the `wp-app-bridge` plugin to be installed and activated on your WordPress site.

For the Application Passwords flow to work on your WordPress site:
1. **WordPress Version**: WordPress 5.6 or higher.
2. **HTTPS/SSL**: WordPress disables Application Passwords over plain HTTP by default. Your site must use `https://` (or have `WP_ENVIRONMENT_TYPE` set to `local`/`development` if testing locally on HTTP).
3. **Authorization Endpoint**: The service constructs links to `{wp_root_url}/wp-admin/authorize-application.php`. Make sure `{wp_root_url}` points directly to the root of your WordPress site (e.g. `https://example.com`).
4. **WP App Bridge Plugin** *(for session storage only)*: Copy `wp-app-bridge/wp-app-bridge.php` to your WordPress site's `wp-content/plugins/` directory and activate it in WP Admin.

### ⚡ One-Liner Remote Plugin Deployment (`deploy_plugin.py`)

Deploy updates to the `wp-app-bridge` WordPress plugin with a single command to any connected WordPress site (such as `tools.belchamber.us`). The deployer integrates seamlessly with `site-manager` config (`sites.yaml` & encrypted credentials):

```bash
# 1. Deploy live update to tools.belchamber.us (auto-commits to GitHub & uploads via SFTP)
python deploy_plugin.py --site tools-belchamber-us

# 2. Dry-run mode to verify connection & files without modifying server:
python deploy_plugin.py --site tools-belchamber-us --dry-run
```

**What the one-liner does automatically:**
1. **GitHub Cloud Backup**: Stages, commits, and pushes plugin updates to `https://github.com/aaronbelchamber/wp-auth-service`.
2. **Site-Manager Integration**: Reads target site SSH details and decrypts credentials directly from `site-manager` (`sites.yaml` & `~/.wp_site_manager/credentials.enc`).
3. **SFTP Direct Upload**: Uploads plugin files via Paramiko SFTP straight to `/wp-content/plugins/wp-app-bridge` on the target server.

---

### Quick Start (One Command)

Run the setup script to install dependencies and start the service:

**Windows:**
```powershell
.\setup.ps1
```

**Linux/Mac:**
```bash
./setup.sh
```

The script will:
1. Check Python installation
2. Install dependencies
3. Create configuration file
4. Start the service

Once running, open `http://localhost:8000` in your browser to access the admin interface, which will guide you through configuring your WordPress site and generating API keys.

### Option 1: Use as a Python Library

Add the library directly to your Python application:

```python
from wp_auth_lib import generate_auth_url, parse_callback_url, validate_credentials

# Generate the WordPress authorization URL
auth_url = generate_auth_url(
    wp_root_url="https://your-site.com",
    app_name="My App",
    callback_url="https://myapp.com/callback"
)

# When WordPress redirects back, extract credentials
callback_result = parse_callback_url(callback_url)
user_login = callback_result.user_login
password = callback_result.password

# Validate the credentials with WordPress
result = validate_credentials(user_login, password, "https://your-site.com")
if result.is_valid:
    print(f"Authenticated as {result.user_profile.username}")
```

### Option 2: Run as a Service (Recommended for Multiple Apps)

Run the service and call it via REST API from any application:

```bash
# Install dependencies
pip install -r requirements.txt

# Start the service
python -m wp_auth_service.main
```

The service will be available at `http://localhost:8000` with an admin interface for configuration and API key management.

## How It Works

1. **Generate Auth URL**: Your app calls the service to get a WordPress authorization URL
2. **User Authorizes**: User clicks the link, logs into WordPress, and approves your app
3. **Receive Credentials**: WordPress redirects back with user credentials
4. **Validate**: Service validates credentials with WordPress and returns user profile

## Features

- **Zero Dependencies**: Core library uses only Python standard library
- **Dual Mode**: Use as embedded library or standalone REST API service
- **Storage Agnostic**: Your app handles token persistence however you prefer
- **Built-in Caching**: In-memory caching with optional Redis support
- **Secure**: API key authentication for service endpoints
- **Admin Interface**: Web UI for configuration and testing
- **Cloud Ready**: Optional Docker deployment (see CLOUD_DEPLOYMENT.md)

## Using the Service

### Admin Interface

When running the service, access the admin interface at `http://localhost:8000` to:

- **Configure** your WordPress site URL, app name, and callback URL
- **Generate API keys** for securing your service endpoints
- **Test authentication** flow end-to-end
- **View the demo** with step-by-step integration examples

### API Endpoints

The service provides these REST API endpoints:

- `POST /api/v1/auth/url` - Generate WordPress authorization URL
- `POST /api/v1/auth/callback` - Parse callback URL to extract credentials
- `POST /api/v1/auth/validate` - Validate credentials with WordPress
- `POST /api/v1/config` - Set WordPress configuration
- `GET /api/v1/config` - Get current configuration
- `POST /api/v1/api-keys/generate` - Generate new API key
- `GET /api/v1/api-keys` - List all API keys
- `DELETE /api/v1/api-keys/{key}` - Revoke an API key

Interactive API documentation is available at `http://localhost:8000/docs`

## Configuration

### Environment Variables

Set these in your `.env` file or as environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `WP_ROOT_URL` | Your WordPress site URL | Yes |
| `APP_NAME` | Your application name | Yes |
| `CALLBACK_URL` | Where WordPress redirects after auth | Yes |
| `API_KEY` | Default API key (can generate via UI) | No |
| `CACHE_TTL` | How long to cache validations (seconds) | No (300) |
| `REDIS_URL` | Redis URL for distributed caching | No |
| `CORS_ORIGINS` | Allowed domains for API calls | No (*) |
| `SERVICE_PORT` | Port for the service | No (8000) |

## Deployment

### Quick Start (Recommended)

Run the setup script - it handles everything:

**Windows:**
```powershell
.\setup.ps1
```

**Linux/Mac:**
```bash
./setup.sh
```

### Manual Setup

If you prefer manual setup:

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and edit configuration
cp .env.example .env
# Edit .env with your WordPress site details

# Start the service
python -m wp_auth_service.main
```

### Cloud Deployment

For cloud hosting, container orchestration, or production environments:

See **[CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md)** for:
- Docker container deployment
- Docker Compose with Redis
- AWS ECS, Google Cloud Run, Azure Container Instances
- Kubernetes deployment
- Production best practices

## API Usage Examples

### Python

```python
import requests

# Generate auth URL
response = requests.post('http://localhost:8000/api/v1/auth/url', json={
    'wp_root_url': 'https://your-site.com',
    'app_name': 'My App',
    'callback_url': 'https://myapp.com/callback'
}, headers={'X-API-Key': 'your-api-key'})
auth_url = response.json()['auth_url']

# Parse callback when WordPress redirects back
response = requests.post('http://localhost:8000/api/v1/auth/callback', json={
    'callback_url': callback_url
})
credentials = response.json()

# Validate credentials
response = requests.post('http://localhost:8000/api/v1/auth/validate', 
    headers={'X-API-Key': 'your-api-key'},
    json={
        'user_login': credentials['user_login'],
        'password': credentials['password'],
        'wp_root_url': 'https://your-site.com'
    }
)
user_profile = response.json()
```

### JavaScript

```javascript
// Generate auth URL
const response = await fetch('http://localhost:8000/api/v1/auth/url', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'your-api-key'
    },
    body: JSON.stringify({
        wp_root_url: 'https://your-site.com',
        app_name: 'My App',
        callback_url: 'https://myapp.com/callback'
    })
});
const {auth_url} = await response.json();

// Parse callback
const callbackResponse = await fetch('http://localhost:8000/api/v1/auth/callback', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({callback_url: callbackUrl})
});
const credentials = await callbackResponse.json();

// Validate credentials
const validateResponse = await fetch('http://localhost:8000/api/v1/auth/validate', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'your-api-key'
    },
    body: JSON.stringify({
        user_login: credentials.user_login,
        password: credentials.password,
        wp_root_url: 'https://your-site.com'
    })
});
const userProfile = await validateResponse.json();
```

### cURL

```bash
# Generate auth URL
curl -X POST http://localhost:8000/api/v1/auth/url \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"wp_root_url":"https://your-site.com","app_name":"My App","callback_url":"https://myapp.com/callback"}'

# Parse callback
curl -X POST http://localhost:8000/api/v1/auth/callback \
  -H "Content-Type: application/json" \
  -d '{"callback_url":"https://myapp.com/callback?user_login=john&password=abc123"}'

# Validate credentials
curl -X POST http://localhost:8000/api/v1/auth/validate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"user_login":"john","password":"abc123","wp_root_url":"https://your-site.com"}'
```

## Troubleshooting

### Service won't start
- Check that port 8000 is not already in use
- Verify Python version is 3.9+
- Ensure all dependencies are installed

### API returns 401/403 errors
- Verify your API key is correct
- Check that the API key hasn't been revoked
- Ensure the `X-API-Key` header is included in requests

### WordPress connection fails
- Verify your WordPress site URL is correct and accessible
- Check that WordPress REST API is enabled
- Ensure your WordPress site supports Application Passwords
- Test network connectivity between service and WordPress site

### Cache issues
- For in-memory cache: restart the service to clear cache
- For Redis: check Redis connection and availability
- Adjust `CACHE_TTL` if caching is causing stale data

## Security Best Practices

1. **Use API Keys**: Always protect your service endpoints with API keys
2. **HTTPS**: Use HTTPS in production for all communications
3. **Restrict CORS**: Set `CORS_ORIGINS` to specific domains in production
4. **Secure Storage**: Store application passwords securely (encrypted database)
5. **Environment Variables**: Never commit `.env` files to version control
6. **Rate Limiting**: Consider rate limiting for production deployments

## Additional Resources

- **Documentation Directory**: [docs/README.md](docs/README.md) — Central documentation hub
- **AI Agent Guidance**: [AGENTS.md](AGENTS.md) — Agent technical reference & quick commands
- **Architecture Guide**: [docs/architecture.md](docs/architecture.md) — component breakdown, data flow, extension points
- **Deployment Guide**: [docs/deployment.md](docs/deployment.md) — 1-liner plugin deployer & Docker guide
- **Implementation Log**: [docs/implementation-log.md](docs/implementation-log.md) — phased build history
- **Interactive API Documentation**: `http://localhost:8000/docs` (when service is running)
- **Admin Dashboard**: `http://localhost:8000` (when service is running)
