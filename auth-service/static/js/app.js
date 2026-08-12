/**
 * Alpine.js app for WordPress Auth Service admin interface.
 *
 * Includes:
 *  - First-run setup wizard (Step 1: API key, Step 2: endpoint)
 *  - Multi-endpoint management (CRUD, clone, confirm, active)
 *  - API key lifecycle management
 */

const SNIPPETS = {
    python: {
        direct: `import requests, urllib.parse

# 1. DIRECT WORDPRESS PRODUCTION CONFIGURATION
WP_ROOT_URL = "\${wpUrl}"
APP_NAME = "\${appName}"
CALLBACK_URL = "\${cbUrl}"

# 2. Direct Auth URL for Browser Authorization
params = urllib.parse.urlencode({"app_name": APP_NAME, "success_url": CALLBACK_URL})
auth_url = f"{WP_ROOT_URL}/wp-admin/authorize-application.php?{params}"
print(f"Direct User Browser to: {auth_url}")

# 3. Direct REST API Credentials Validation (Basic Auth)
USER_LOGIN = "USER_LOGIN_FROM_CALLBACK"
APP_PASSWORD = "PASSWORD_TOKEN_FROM_CALLBACK"

res = requests.get(
    f"{WP_ROOT_URL}/wp-json/wp/v2/users/me?context=edit",
    auth=(USER_LOGIN, APP_PASSWORD)
)
print("User Profile Data:", res.json())`,
        proxy: `import requests

# 1. LOCAL SERVICE PROXY CONFIGURATION
WP_ROOT_URL = "\${wpUrl}"
AUTH_SERVICE_URL = "http://localhost:8000"

# 2. Step 1: Request Authorization URL via Local Proxy
res = requests.post(f"{AUTH_SERVICE_URL}/api/v1/auth/url", json={
    "wp_root_url": WP_ROOT_URL,
    "app_name": "\${appName}",
    "callback_url": "\${cbUrl}"
})
auth_url = res.json()["auth_url"]
print(f"Direct User Browser to: {auth_url}")

# 3. Step 3: Validate Credentials via Local Proxy
credentials = {
    "wp_root_url": WP_ROOT_URL,
    "user_login": "USER_LOGIN_FROM_CALLBACK",
    "password": "PASSWORD_TOKEN_FROM_CALLBACK"
}
val_res = requests.post(f"{AUTH_SERVICE_URL}/api/v1/auth/validate", json=credentials)
user_data = val_res.json()
print("Validated User Data:", user_data)`
    },
    php: {
        direct: `<?php
// DIRECT WORDPRESS PRODUCTION CONFIGURATION
$wp_root_url = '\${wpUrl}';
$app_name = urlencode('\${appName}');
$callback_url = urlencode('\${cbUrl}');

// 1. Direct Auth URL
$auth_url = "$wp_root_url/wp-admin/authorize-application.php?app_name=$app_name&success_url=$callback_url";

// 2. Direct REST API Call
$username = 'USER_LOGIN_FROM_CALLBACK';
$app_password = 'PASSWORD_TOKEN_FROM_CALLBACK';

$ch = curl_init("$wp_root_url/wp-json/wp/v2/users/me?context=edit");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_USERPWD, "$username:$app_password");
$user_profile = json_decode(curl_exec($ch), true);
curl_close($ch);`,
        proxy: `<?php
// LOCAL SERVICE PROXY CONFIGURATION
$wp_root_url = '\${wpUrl}';
$auth_service_url = 'http://localhost:8000';

// 1. Request Auth URL via Proxy
$ch = curl_init("$auth_service_url/api/v1/auth/url");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    'wp_root_url' => $wp_root_url,
    'app_name' => '\${appName}',
    'callback_url' => '\${cbUrl}'
]));
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
$response = json_decode(curl_exec($ch), true);
$auth_url = $response['auth_url'];
curl_close($ch);`
    },
    node: {
        direct: `const axios = require('axios');

const WP_ROOT_URL = '\${wpUrl}';

// 1. Direct Auth URL
function getDirectAuthUrl() {
  const params = new URLSearchParams({ app_name: '\${appName}', success_url: '\${cbUrl}' });
  return \`\${WP_ROOT_URL}/wp-admin/authorize-application.php?\${params}\`;
}

// 2. Direct WordPress REST API Request
async function validateDirectWP(username, appPassword) {
  const authHeader = Buffer.from(\`\${username}:\${appPassword}\`).toString('base64');
  const { data } = await axios.get(\`\${WP_ROOT_URL}/wp-json/wp/v2/users/me?context=edit\`, {
    headers: { Authorization: \`Basic \${authHeader}\` }
  });
  return data;
}`,
        proxy: `const axios = require('axios');

const WP_ROOT_URL = '\${wpUrl}';
const AUTH_SERVICE_URL = 'http://localhost:8000';

// 1. Generate Auth URL via Proxy
async function getAuthUrl() {
  const { data } = await axios.post(\`\${AUTH_SERVICE_URL}/api/v1/auth/url\`, {
    wp_root_url: WP_ROOT_URL,
    app_name: '\${appName}',
    callback_url: '\${cbUrl}'
  });
  return data.auth_url;
}

// 2. Validate Credentials via Proxy
async function validateCredentials(userLogin, password) {
  const { data } = await axios.post(\`\${AUTH_SERVICE_URL}/api/v1/auth/validate\`, {
    wp_root_url: WP_ROOT_URL,
    user_login: userLogin,
    password: password
  });
  return data;
}`
    },
    flutter: {
        direct: `import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:url_launcher/url_launcher.dart';

const String wpRootUrl = '\${wpUrl}';

// 1. Launch Direct WordPress Authorization URL
Future<void> startDirectWPAuth() async {
  final Uri authUri = Uri.parse('$wpRootUrl/wp-admin/authorize-application.php').replace(
    queryParameters: {'app_name': '\${appName}', 'success_url': '\${cbUrl}'},
  );
  await launchUrl(authUri, mode: LaunchMode.externalApplication);
}

// 2. Direct WP Basic Auth Request
Future<Map<String, dynamic>> validateDirect(String userLogin, String appPassword) async {
  final String basicAuth = 'Basic ' + base64Encode(utf8.encode('$userLogin:$appPassword'));
  final res = await http.get(
    Uri.parse('$wpRootUrl/wp-json/wp/v2/users/me?context=edit'),
    headers: {'Authorization': basicAuth},
  );
  return jsonDecode(res.body);
}`,
        proxy: `import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:url_launcher/url_launcher.dart';

const String wpRootUrl = '\${wpUrl}';
const String authServiceUrl = 'http://localhost:8000';

// 1. Request Auth URL & Launch System Browser
Future<void> startWordPressAuth() async {
  final response = await http.post(
    Uri.parse('$authServiceUrl/api/v1/auth/url'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'wp_root_url': wpRootUrl,
      'app_name': '\${appName}',
      'callback_url': '\${cbUrl}',
    }),
  );

  final authUrl = jsonDecode(response.body)['auth_url'];
  await launchUrl(Uri.parse(authUrl), mode: LaunchMode.externalApplication);
}`
    }
};

function authApp() {
    return {
        // --- Navigation ---
        currentTab: 'endpoints',

        // --- Onboarding Wizard State ---
        onboardStatus: { step1: false, step2: false, step3: false, step4: false },
        showPluginGuide: false,
        onboardLogs: [],
        capturedCreds: null,
        _credPollInterval: null,

        // --- Wizard ---
        isFirstRun: false,
        wizardStep: 1,     // 1 = generate key, 2 = add endpoint
        wizardKeyName: 'admin',
        wizardKeyGenerated: false,

        // --- Endpoints ---
        endpoints: [],
        activeEndpoint: null,
        selectedEndpointId: '',
        showEndpointForm: false,
        formEndpoint: { id: null, name: '', wp_root_url: '', app_name: '', callback_url: '', is_active: false },

        // --- API Keys ---
        apiKey: localStorage.getItem('wp_auth_api_key') || '',
        apiKeys: [],
        selectedKeys: [],
        newKeyName: '',
        generatedApiKey: '',
        showApiKeyModal: false,

        // --- Test Auth ---
        testAuthUrl: '',
        testCallbackUrl: '',
        parsedCallback: {},
        validationResult: {},
        codeLanguage: 'python',
        testSubTab: 'sandbox',           // 'sandbox' or 'monitor'
        authArchitectureMode: 'proxy',   // 'proxy' (localhost:8000) or 'direct' (WordPress core direct)

        // --- Activity Logs ---
        activityLogs: [],
        activityFilter: 'all',
        selectedLog: null,

        // --- UI ---
        message: '',
        messageType: 'success',

        // =========================================================
        // Helper Methods
        // =========================================================
        authHeaders(extra = {}) {
            const headers = { ...extra };
            if (this.apiKey) {
                headers['X-API-Key'] = this.apiKey;
            }
            return headers;
        },

        _getOnboardStorageKey() {
            const ep = this.getTargetEndpoint();
            return (ep && ep.id) ? ep.id : 'default';
        },

        _validateEndpointForm() {
            return Boolean(
                this.formEndpoint.name &&
                this.formEndpoint.wp_root_url &&
                this.formEndpoint.app_name &&
                this.formEndpoint.callback_url
            );
        },

        _focusEndpointNameInput() {
            setTimeout(() => {
                const el = document.getElementById('profile-name-input');
                if (el) {
                    el.focus();
                    el.select();
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }, 50);
        },

        tabClass(tabName) {
            return this.currentTab === tabName
                ? 'border-b-2 border-blue-500 text-blue-600 font-semibold'
                : 'text-slate-500 hover:text-slate-800';
        },

        langTabClass(langName) {
            return this.codeLanguage === langName
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-400 hover:text-white hover:bg-slate-800';
        },

        epStatusClass(ep) {
            if (!ep) return 'bg-slate-100 text-slate-600 border-slate-300';
            return ep.status === 'confirmed'
                ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
                : 'bg-amber-100 text-amber-700 border-amber-300';
        },

        epStatusLabel(ep) {
            if (!ep) return '—';
            return ep.status === 'confirmed' ? '✓ Confirmed' : '⚠ Unconfirmed';
        },

        // =========================================================
        // Navigation & Clean Path Routing (HTML5 History API)
        // =========================================================
        switchTab(tabName, pushState = true) {
            if (this._credPollInterval) {
                clearInterval(this._credPollInterval);
                this._credPollInterval = null;
            }
            this.currentTab = tabName;
            this.selectedLog = null;
            if (tabName !== 'onboarding') {
                this.isFirstRun = false;
            }

            const targetPath = tabName === 'onboarding' ? '/onboarding' : `/${tabName}`;
            if (pushState && window.location.pathname !== targetPath) {
                try {
                    window.history.pushState({ tab: tabName }, '', targetPath);
                } catch (e) {
                    console.warn('Could not pushState:', e);
                }
            }
            if (tabName === 'endpoints') {
                this.loadEndpoints();
            } else if (tabName === 'api-keys') {
                this.loadApiKeys();
            } else if (tabName === 'activity') {
                this.loadActivityLogs();
            }
        },

        // =========================================================
        // Init
        // =========================================================
        async initApp() {
            this.isFirstRun = false;
            this.selectedLog = null;

            // Read initial tab from URL path (e.g. /endpoints or /activity)
            const pathTab = window.location.pathname.replace(/^\//, '').split('/')[0];
            const validTabs = ['onboarding', 'endpoints', 'api-keys', 'activity', 'test'];
            
            if (validTabs.includes(pathTab)) {
                this.currentTab = pathTab;
            } else {
                this.currentTab = 'onboarding';
                if (window.location.pathname === '/' || !pathTab) {
                    try {
                        window.history.replaceState({ tab: 'onboarding' }, '', '/onboarding');
                    } catch (e) {}
                }
            }

            try {
                await this.loadEndpoints();
            } catch (e) {
                console.warn('Could not load endpoints on init:', e);
            }
            try {
                await this.loadApiKeys();
            } catch (e) {
                console.warn('Could not load API keys on init:', e);
            }

            // Only trigger setup wizard mode if user is on onboarding tab AND there are zero endpoints AND zero API keys
            if (this.currentTab === 'onboarding' && this.endpoints.length === 0 && this.apiKeys.length === 0 && !this.apiKey) {
                this.isFirstRun = true;
            } else {
                this.isFirstRun = false;
            }

            await this.loadActivityLogs();

            window.addEventListener('message', (event) => {
                if (event.data && event.data.type === 'WP_AUTH_SUCCESS') {
                    this.checkCapturedCredentials();
                    this.loadActivityLogs();
                }
            });

            window.addEventListener('popstate', () => {
                const pTab = window.location.pathname.replace(/^\//, '').split('/')[0];
                if (validTabs.includes(pTab)) {
                    this.switchTab(pTab, false);
                } else {
                    this.switchTab('onboarding', false);
                }
            });

            this.loadOnboardState();
            await this.checkCapturedCredentials();
            const ep = this.getTargetEndpoint();
            if (ep && ep.id) {
                this.runStep1PluginCheck({ silent: true });
            }
        },

        async loadActivityLogs() {
            try {
                const res = await fetch(`/api/v1/activity?limit=50&filter_type=${this.activityFilter}`, {
                    headers: this.authHeaders()
                });
                if (res.ok) {
                    this.activityLogs = await res.json();
                }
            } catch (e) {
                console.warn('Could not load activity logs:', e);
            }
        },

        async clearActivityLogs(testOnly = false) {
            const promptMsg = testOnly ? 'Delete all test and probe log entries?' : 'Delete ALL activity logs?';
            if (!confirm(promptMsg)) return;
            try {
                const res = await fetch(`/api/v1/activity?test_only=${testOnly}`, {
                    method: 'DELETE',
                    headers: this.authHeaders()
                });
                if (res.ok) {
                    const data = await res.json();
                    this.showMessage(`Deleted ${data.deleted_count} log entries.`, 'success');
                    await this.loadActivityLogs();
                }
            } catch (e) {
                this.showMessage('Error clearing logs: ' + e.message, 'error');
            }
        },

        clearOnboardLogs() {
            this.onboardLogs = [];
            this.showMessage('Diagnostics console cleared', 'info');
        },

        openLogDetails(log) {
            this.selectedLog = log;
        },

        saveOnboardState() {
            const epId = this._getOnboardStorageKey();
            try {
                localStorage.setItem(`wp_auth_onboard_status_${epId}`, JSON.stringify(this.onboardStatus));
                if (this.capturedCreds) {
                    localStorage.setItem(`wp_auth_captured_creds_${epId}`, JSON.stringify(this.capturedCreds));
                }
            } catch (e) {
                console.warn('Could not save onboard state:', e);
            }
        },

        loadOnboardState() {
            const epId = this._getOnboardStorageKey();
            try {
                const savedStatus = localStorage.getItem(`wp_auth_onboard_status_${epId}`);
                if (savedStatus) {
                    const parsed = JSON.parse(savedStatus);
                    this.onboardStatus = Object.assign({ step1: false, step2: false, step3: false, step4: false }, parsed);
                }
                const savedCreds = localStorage.getItem(`wp_auth_captured_creds_${epId}`);
                if (savedCreds) {
                    const parsedCreds = JSON.parse(savedCreds);
                    if (parsedCreds && parsedCreds.user_login) {
                        this.capturedCreds = parsedCreds;
                        this.onboardStatus.step2 = true;
                    }
                }
            } catch (e) {
                console.warn('Could not load onboard state:', e);
            }
        },

        async checkCapturedCredentials() {
            try {
                const response = await fetch('/api/v1/auth/latest-credentials');
                if (response.ok) {
                    const data = await response.json();
                    if (data && (data.status === 'captured' || data.user_login) && data.user_login) {
                        this.capturedCreds = data;
                        this.onboardStatus.step2 = true;
                        if (!this.parsedCallback || !this.parsedCallback.user_login) {
                            this.parsedCallback = {
                                user_login: data.user_login,
                                password: data.password,
                                site_url: data.site_url || null,
                                is_valid: true
                            };
                        }
                        this.saveOnboardState();
                        return true;
                    }
                }
            } catch (e) {
                console.warn('Could not check captured credentials:', e);
            }
            if (this.capturedCreds && this.capturedCreds.user_login) {
                this.onboardStatus.step2 = true;
                return true;
            }
            return false;
        },

        // =========================================================
        // Wizard
        // =========================================================
        async wizardGenerateKey() {
            const name = (this.wizardKeyName || 'admin').trim();
            try {
                const response = await fetch(`/api/v1/api-keys/generate?name=${encodeURIComponent(name)}`, {
                    method: 'POST'
                });
                if (!response.ok) throw new Error('Failed to generate key');
                const data = await response.json();
                this.generatedApiKey = data.api_key;
                this.apiKey = data.api_key;
                localStorage.setItem('wp_auth_api_key', data.api_key);
                this.wizardKeyGenerated = true;
            } catch (e) {
                this.showMessage('Failed to generate key: ' + e.message, 'error');
            }
        },

        wizardCopyKey() {
            navigator.clipboard.writeText(this.generatedApiKey);
            this.showMessage('Key copied!', 'success');
        },

        wizardNextStep() {
            this.wizardStep = 2;
            this.formEndpoint = { id: null, name: 'My WordPress Site', wp_root_url: '', app_name: 'My App', callback_url: '', is_active: true };
            this._focusEndpointNameInput();
        },

        async wizardSaveEndpoint() {
            if (!this._validateEndpointForm()) {
                this.showMessage('Please fill in all fields', 'error');
                return;
            }
            try {
                const response = await fetch('/api/v1/endpoints', {
                    method: 'POST',
                    headers: this.authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ ...this.formEndpoint, is_active: true })
                });
                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }
                this.isFirstRun = false;
                await this.loadEndpoints();
                await this.loadApiKeys();
                this.showMessage('Setup complete! Your first endpoint is saved.', 'success');
            } catch (e) {
                this.showMessage('Error saving endpoint: ' + e.message, 'error');
            }
        },

        wizardSkipEndpoint() {
            this.isFirstRun = false;
            this.loadEndpoints();
            this.loadApiKeys();
        },

        // =========================================================
        // Session Key
        // =========================================================
        setApiKey(key) {
            this.apiKey = (key || '').trim();
            if (this.apiKey) {
                localStorage.setItem('wp_auth_api_key', this.apiKey);
                this.showMessage('Session key updated', 'success');
            } else {
                localStorage.removeItem('wp_auth_api_key');
                this.showMessage('Session key cleared', 'info');
            }
            this.showApiKeyModal = false;
            this.loadEndpoints();
            this.loadApiKeys();
        },

        // =========================================================
        // Endpoints
        // =========================================================
        async loadEndpoints() {
            try {
                const response = await fetch('/api/v1/endpoints', { headers: this.authHeaders() });
                if (!response.ok) {
                    if (response.status === 401 || response.status === 403) {
                        this.showMessage('Authentication failed — check your Session Key.', 'error');
                    }
                    return;
                }
                const data = await response.json();
                this.endpoints = data || [];
                this.activeEndpoint = this.endpoints.find(e => e.is_active) || (this.endpoints.length ? this.endpoints[0] : null);
                if (this.endpoints.length && !this.selectedEndpointId) {
                    this.selectedEndpointId = this.activeEndpoint ? this.activeEndpoint.id : this.endpoints[0].id;
                }
            } catch (e) {
                console.error('Error loading endpoints:', e);
            }
        },

        openNewEndpointForm() {
            this.formEndpoint = {
                id: null,
                name: 'New WordPress Site',
                wp_root_url: '',
                app_name: 'My Application',
                callback_url: '',
                is_active: this.endpoints.length === 0
            };
            this.showEndpointForm = true;
            this._focusEndpointNameInput();
        },

        editEndpoint(ep) {
            this.formEndpoint = JSON.parse(JSON.stringify(ep));
            this.showEndpointForm = true;
            this._focusEndpointNameInput();
        },

        cancelEndpointForm() {
            this.showEndpointForm = false;
        },

        async saveEndpoint() {
            if (!this._validateEndpointForm()) {
                this.showMessage('Please complete all required fields', 'error');
                return;
            }
            const isEdit = Boolean(this.formEndpoint.id);
            const url = isEdit ? `/api/v1/endpoints/${this.formEndpoint.id}` : '/api/v1/endpoints';
            const method = isEdit ? 'PUT' : 'POST';
            try {
                const response = await fetch(url, {
                    method,
                    headers: this.authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({
                        name: this.formEndpoint.name,
                        wp_root_url: this.formEndpoint.wp_root_url,
                        app_name: this.formEndpoint.app_name,
                        callback_url: this.formEndpoint.callback_url,
                        is_active: this.formEndpoint.is_active
                    })
                });
                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.detail || `HTTP ${response.status}`);
                }
                const savedEp = await response.json();
                this.showEndpointForm = false;
                this.showMessage(`Endpoint '${savedEp.name}' saved (${savedEp.status})`, 'success');
                await this.loadEndpoints();
            } catch (e) {
                this.showMessage(`Save failed: ${e.message}`, 'error');
            }
        },

        async cloneEndpoint(id) {
            try {
                const response = await fetch(`/api/v1/endpoints/${id}/clone`, {
                    method: 'POST',
                    headers: this.authHeaders()
                });
                if (!response.ok) throw new Error('Failed to clone endpoint');
                const cloned = await response.json();
                this.showMessage(`Cloned as '${cloned.name}'`, 'success');
                await this.loadEndpoints();
                this.editEndpoint(cloned);
            } catch (e) {
                this.showMessage('Clone error: ' + e.message, 'error');
            }
        },

        async deleteEndpoint(id) {
            if (!confirm('Delete this endpoint profile?')) return;
            try {
                const response = await fetch(`/api/v1/endpoints/${id}`, {
                    method: 'DELETE',
                    headers: this.authHeaders()
                });
                if (!response.ok) throw new Error('Failed to delete');
                this.showMessage('Endpoint deleted', 'success');
                await this.loadEndpoints();
            } catch (e) {
                this.showMessage('Delete error: ' + e.message, 'error');
            }
        },

        async makeActiveEndpoint(id) {
            try {
                const response = await fetch(`/api/v1/endpoints/${id}/active`, {
                    method: 'POST',
                    headers: this.authHeaders()
                });
                if (!response.ok) throw new Error('Failed to set active');
                const active = await response.json();
                this.showMessage(`'${active.name}' is now active`, 'success');
                await this.loadEndpoints();
            } catch (e) {
                this.showMessage('Error: ' + e.message, 'error');
            }
        },

        async confirmEndpoint(id) {
            this.showMessage('Testing reachability…', 'info');
            try {
                const response = await fetch(`/api/v1/endpoints/${id}/confirm`, {
                    method: 'POST',
                    headers: this.authHeaders()
                });
                if (!response.ok) throw new Error('Check failed');
                const updated = await response.json();
                if (updated.status === 'confirmed') {
                    this.showMessage(`✓ '${updated.name}' is reachable!`, 'success');
                } else {
                    this.showMessage(`⚠ '${updated.name}' could not be reached (check URL)`, 'error');
                }
                await this.loadEndpoints();
            } catch (e) {
                this.showMessage('Reachability error: ' + e.message, 'error');
            }
        },

        // =========================================================
        // API Keys
        // =========================================================
        async loadApiKeys() {
            try {
                const response = await fetch('/api/v1/api-keys', { headers: this.authHeaders() });
                if (!response.ok) return;
                const data = await response.json();
                this.apiKeys = data.keys || [];
            } catch (e) {
                console.error('Error loading API keys:', e);
            }
        },

        async generateApiKey() {
            if (!this.newKeyName) { this.showMessage('Enter a key name', 'error'); return; }
            try {
                const response = await fetch(`/api/v1/api-keys/generate?name=${encodeURIComponent(this.newKeyName)}`, {
                    method: 'POST',
                    headers: this.authHeaders()
                });
                if (!response.ok) throw new Error('Failed to generate key');
                const data = await response.json();
                this.generatedApiKey = data.api_key;
                this.apiKey = data.api_key;
                localStorage.setItem('wp_auth_api_key', data.api_key);
                this.newKeyName = '';
                await this.loadApiKeys();
                await this.loadEndpoints();
                this.showMessage('Key generated successfully and set as session key', 'success');
            } catch (e) {
                this.showMessage('Error generating key: ' + e.message, 'error');
            }
        },

        copyApiKey() {
            navigator.clipboard.writeText(this.generatedApiKey);
            this.showMessage('Copied to clipboard!', 'success');
        },

        async revokeApiKey(keyPreview) {
            if (!confirm(`Revoke API key '${keyPreview}'? This cannot be undone.`)) return;
            try {
                const res = await fetch(`/api/v1/api-keys/${keyPreview}`, {
                    method: 'DELETE',
                    headers: this.authHeaders()
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                this.selectedKeys = this.selectedKeys.filter(k => k !== keyPreview);
                await this.loadApiKeys();
                this.showMessage(`Key '${keyPreview}' revoked successfully`, 'success');
            } catch (e) {
                this.showMessage('Error revoking key: ' + e.message, 'error');
            }
        },

        async bulkRevokeKeys() {
            const count = this.selectedKeys.length;
            if (!count) return;
            if (!confirm(`Permanently delete ${count} key(s)?`)) return;
            const headers = this.authHeaders();
            const keysToRevoke = [...this.selectedKeys];
            const results = await Promise.allSettled(
                keysToRevoke.map(preview =>
                    fetch(`/api/v1/api-keys/${preview}`, { method: 'DELETE', headers })
                )
            );
            const failed = results.filter(r => r.status === 'rejected' || (r.value && !r.value.ok)).length;
            this.selectedKeys = [];
            await this.loadApiKeys();
            const msg = failed
                ? `Deleted ${count - failed} of ${count} keys (${failed} failed)`
                : `Deleted ${count} key(s)`;
            this.showMessage(msg, failed ? 'error' : 'success');
        },

        // =========================================================
        // Test Auth
        // =========================================================
        getTargetEndpoint() {
            if (this.selectedEndpointId) {
                const found = this.endpoints.find(e => e.id === this.selectedEndpointId);
                if (found) return found;
            }
            return this.activeEndpoint || {};
        },

        async generateTestAuthUrl() {
            const ep = this.getTargetEndpoint();
            try {
                const response = await fetch('/api/v1/auth/url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ wp_root_url: ep.wp_root_url || '', app_name: ep.app_name || '', callback_url: ep.callback_url || '' })
                });
                if (!response.ok) throw new Error('Failed to generate auth URL');
                const data = await response.json();
                this.testAuthUrl = data.auth_url;
            } catch (e) {
                this.showMessage('Error: ' + e.message, 'error');
            }
        },

        async parseTestCallback() {
            if (!this.testCallbackUrl || !this.testCallbackUrl.trim()) {
                this.showMessage('Please paste a callback URL first.', 'error');
                return;
            }
            try {
                const response = await fetch('/api/v1/auth/callback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ callback_url: this.testCallbackUrl.trim() })
                });
                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.detail || 'Failed to parse callback');
                }
                const data = await response.json();
                this.parsedCallback = data;

                if (data.is_valid && data.user_login) {
                    this.showMessage(`✓ Successfully parsed credentials for '${data.user_login}'!`, 'success');
                } else {
                    this.showMessage('⚠ Could not extract credentials (user_login & password) from the URL.', 'error');
                }
            } catch (e) {
                this.showMessage('Error parsing callback: ' + e.message, 'error');
            }
        },

        async validateTestCredentials() {
            if (!this.parsedCallback?.user_login) { this.showMessage('Parse a callback URL first', 'error'); return; }
            const ep = this.getTargetEndpoint();
            const wpRootUrl = ep.wp_root_url || this.parsedCallback.site_url || '';
            if (!wpRootUrl) {
                this.showMessage('Please select an Endpoint Profile or use a callback URL with site_url', 'error');
                return;
            }
            try {
                const response = await fetch('/api/v1/auth/validate', {
                    method: 'POST',
                    headers: this.authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ user_login: this.parsedCallback.user_login, password: this.parsedCallback.password, wp_root_url: wpRootUrl })
                });
                if (!response.ok) throw new Error('Failed to validate credentials');
                this.validationResult = await response.json();
            } catch (e) {
                this.showMessage('Error: ' + e.message, 'error');
            }
        },

        getSnippet(lang) {
            const ep = this.getTargetEndpoint();
            const wpUrl = (ep.wp_root_url || 'https://your-wordpress-site.com').replace(/\/$/, '');
            const appName = ep.app_name || 'My Application';
            const cbUrl = ep.callback_url || 'http://localhost:8000/auth/callback';
            const mode = this.authArchitectureMode === 'direct' ? 'direct' : 'proxy';

            const template = SNIPPETS[lang]?.[mode] ?? '';
            return template
                .replace(/\$\{wpUrl\}/g, wpUrl)
                .replace(/\$\{appName\}/g, appName)
                .replace(/\$\{cbUrl\}/g, cbUrl);
        },

        // =========================================================
        // Onboarding Wizard Methods
        // =========================================================
        addLog(text, type = 'info') {
            this.onboardLogs.push({ text: `[${new Date().toLocaleTimeString()}] ${text}`, type });
        },

        async runStep1PluginCheck(options = {}) {
            const isSilent = Boolean(options && options.silent);
            const ep = this.getTargetEndpoint();
            if (!ep || !ep.id) {
                if (!isSilent) this.addLog('Error: No target endpoint profile selected or active.', 'error');
                return;
            }
            if (!isSilent) this.addLog(`Probing plugin health on ${ep.wp_root_url}...`);
            try {
                const res = await fetch(`/api/v1/endpoints/${ep.id}/plugin-check`, { method: 'POST' });
                const data = await res.json();
                if (data.is_plugin_active) {
                    this.onboardStatus.step1 = true;
                    this.showPluginGuide = false;
                    if (!isSilent) {
                        this.addLog(`✓ Plugin bridge active! Version: ${data.details.version}`, 'success');
                    }
                    this.saveOnboardState();
                } else {
                    if (!isSilent) {
                        this.onboardStatus.step1 = false;
                        this.showPluginGuide = true;
                        this.addLog(`❌ Plugin check failed (HTTP ${data.status_code || 'unreachable'}). Plugin not active or installed on site.`, 'error');
                        this.addLog(`👉 Follow the installation guide shown in Step 1 to download and upload the plugin zip to WordPress.`, 'info');
                        this.saveOnboardState();
                    }
                }
            } catch (e) {
                if (!isSilent) {
                    this.onboardStatus.step1 = false;
                    this.showPluginGuide = true;
                    this.addLog(`❌ Network error probing plugin: ${e.message}`, 'error');
                    this.addLog(`👉 Follow the installation guide shown in Step 1 to download and upload the plugin zip to WordPress.`, 'info');
                    this.saveOnboardState();
                }
            }
        },

        async runStep2OAuthFlow() {
            const ep = this.getTargetEndpoint();
            if (!ep || !ep.wp_root_url) {
                this.addLog('Error: No target endpoint profile configured.', 'error');
                return;
            }
            const currentOrigin = window.location.origin;
            const callbackUrl = ep.callback_url || `${currentOrigin}/auth`;
            this.addLog(`Generating Auth URL with callback to ${callbackUrl}...`);

            if (this._credPollInterval) {
                clearInterval(this._credPollInterval);
                this._credPollInterval = null;
            }

            try {
                const res = await fetch('/api/v1/auth/url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        wp_root_url: ep.wp_root_url,
                        app_name: ep.app_name || 'My App',
                        callback_url: callbackUrl
                    })
                });
                const data = await res.json();
                if (data.auth_url) {
                    this.addLog(`Opening authorization window...`);
                    window.open(data.auth_url, '_blank');
                    this.addLog(`Waiting for browser callback at 127.0.0.1:8000...`);
                    
                    // Poll for captured credentials with clean handle
                    let attempts = 0;
                    this._credPollInterval = setInterval(async () => {
                        attempts++;
                        const credRes = await fetch('/api/v1/auth/latest-credentials');
                        const credData = await credRes.json();
                        if (credData.status === 'captured') {
                            if (this._credPollInterval) {
                                clearInterval(this._credPollInterval);
                                this._credPollInterval = null;
                            }
                            this.capturedCreds = credData;
                            this.onboardStatus.step2 = true;
                            this.saveOnboardState();
                            this.addLog(`✓ Received callback for user '${credData.user_login}'! Credentials captured.`, 'success');
                        } else if (attempts > 30) {
                            if (this._credPollInterval) {
                                clearInterval(this._credPollInterval);
                                this._credPollInterval = null;
                            }
                            this.addLog(`⚠️ Timed out waiting for callback redirect.`, 'error');
                        }
                    }, 2000);
                }
            } catch (e) {
                this.addLog(`❌ Error starting auth flow: ${e.message}`, 'error');
            }
        },

        async runStep3Validate() {
            if (!this.capturedCreds || !this.capturedCreds.user_login) {
                await this.checkCapturedCredentials();
            }
            if (!this.capturedCreds || !this.capturedCreds.user_login) {
                this.addLog('Error: Complete Step 2 first to capture credentials.', 'error');
                return;
            }
            const ep = this.getTargetEndpoint();
            this.addLog(`Validating credentials for '${this.capturedCreds.user_login}' against WP REST API...`);
            try {
                const res = await fetch('/api/v1/auth/validate', {
                    method: 'POST',
                    headers: this.authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({
                        user_login: this.capturedCreds.user_login,
                        password: this.capturedCreds.password,
                        wp_root_url: ep.wp_root_url
                    })
                });
                const data = await res.json();
                if (data.is_valid) {
                    this.onboardStatus.step3 = true;
                    this.saveOnboardState();
                    this.addLog(`✓ Credentials verified! User ID: ${data.user_id}, Roles: ${data.roles.join(', ')}`, 'success');
                } else {
                    this.onboardStatus.step3 = false;
                    this.saveOnboardState();
                    const err = data.error_message || data.detail || 'Invalid credentials';
                    this.addLog(`❌ Credential validation failed: ${err}`, 'error');
                }
            } catch (e) {
                this.addLog(`❌ Error validating credentials: ${e.message}`, 'error');
            }
        },

        async runStep4AppDataTest() {
            if (!this.capturedCreds || !this.capturedCreds.user_login) {
                await this.checkCapturedCredentials();
            }
            if (!this.capturedCreds || !this.capturedCreds.user_login) {
                this.addLog('Error: Credentials required. Complete Step 2 & 3 first.', 'error');
                return;
            }
            const ep = this.getTargetEndpoint();
            const testKey = 'onboarding_test_' + Date.now();
            const testPayload = { message: 'Hello from Auth Service!', timestamp: Date.now() };

            this.addLog(`Writing session payload to WP DB via plugin bridge...`);
            try {
                const saveRes = await fetch('/api/v1/session/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        wp_root_url: ep.wp_root_url,
                        user_login: this.capturedCreds.user_login,
                        password: this.capturedCreds.password,
                        app_id: ep.app_name || 'My App',
                        session_key: testKey,
                        payload: testPayload
                    })
                });
                const saveResult = await saveRes.json();
                if (!saveResult.success) throw new Error(saveResult.detail || 'Save failed');
                this.addLog(`✓ Saved test payload into WordPress belchamber_auth_sessions table.`, 'success');

                this.addLog(`Reading back session payload from WordPress...`);
                const getRes = await fetch('/api/v1/session/get', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        wp_root_url: ep.wp_root_url,
                        user_login: this.capturedCreds.user_login,
                        password: this.capturedCreds.password,
                        app_id: ep.app_name || 'My App',
                        session_key: testKey
                    })
                });
                const getResult = await getRes.json();
                if (getResult.success && getResult.session?.payload?.message === testPayload.message) {
                    this.onboardStatus.step4 = true;
                    this.saveOnboardState();
                    this.addLog(`🎉 Full Round-Trip Success! Data written to and read from WP DB seamlessly.`, 'success');
                } else {
                    this.addLog(`❌ Session fetch payload mismatch or failed.`, 'error');
                }
            } catch (e) {
                this.addLog(`❌ Data loop test failed: ${e.message}`, 'error');
            }
        },

        // =========================================================
        // Utilities
        // =========================================================
        showMessage(msg, type) {
            this.message = msg;
            this.messageType = type;
            setTimeout(() => { this.message = ''; }, 6000);
        },

        formatDate(ds) {
            if (!ds) return '—';
            return new Date(ds).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
        },

        copyToClipboard(text) {
            navigator.clipboard.writeText(text);
            this.showMessage('Copied', 'success');
        }
    };
}

