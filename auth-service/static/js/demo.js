/**
 * Alpine.js components for WordPress Auth Service demo interface.
 */

function demoApp() {
    return {
        currentStep: 1,
        demoConfig: {
            wp_root_url: '',
            app_name: '',
            callback_url: ''
        },
        demoAuthUrl: '',
        simulatedCallback: '',
        parsedDemoCallback: null,
        demoValidationResult: null,

        initDemo() {
            // Load config from localStorage if available
            const savedConfig = localStorage.getItem('wp_auth_config');
            if (savedConfig) {
                this.demoConfig = JSON.parse(savedConfig);
            }
        },

        async generateDemoAuthUrl() {
            try {
                const response = await fetch('/api/v1/auth/url', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.demoConfig)
                });

                if (!response.ok) {
                    throw new Error('Failed to generate auth URL');
                }

                const data = await response.json();
                this.demoAuthUrl = data.auth_url;
            } catch (error) {
                alert('Error generating auth URL: ' + error.message);
            }
        },

        async parseDemoCallback() {
            if (!this.simulatedCallback) {
                alert('Please enter a callback URL');
                return;
            }

            try {
                const response = await fetch('/api/v1/auth/callback', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        callback_url: this.simulatedCallback
                    })
                });

                if (!response.ok) {
                    throw new Error('Failed to parse callback');
                }

                const data = await response.json();
                this.parsedDemoCallback = data;
            } catch (error) {
                alert('Error parsing callback: ' + error.message);
            }
        },

        async validateDemoCredentials() {
            if (!this.parsedDemoCallback) {
                alert('Please parse a callback URL first');
                return;
            }

            const apiKey = localStorage.getItem('wp_auth_api_key');
            if (!apiKey) {
                alert('Please set an API key in the Admin panel first');
                return;
            }

            try {
                const response = await fetch('/api/v1/auth/validate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': apiKey
                    },
                    body: JSON.stringify({
                        user_login: this.parsedDemoCallback.user_login,
                        password: this.parsedDemoCallback.password,
                        wp_root_url: this.demoConfig.wp_root_url
                    })
                });

                if (!response.ok) {
                    throw new Error('Failed to validate credentials');
                }

                const data = await response.json();
                this.demoValidationResult = data;
            } catch (error) {
                alert('Error validating credentials: ' + error.message);
            }
        },

        resetDemo() {
            this.currentStep = 1;
            this.demoAuthUrl = '';
            this.simulatedCallback = '';
            this.parsedDemoCallback = null;
            this.demoValidationResult = null;
        },

        copyToClipboard(text) {
            navigator.clipboard.writeText(text);
            alert('Copied to clipboard');
        }
    };
}
