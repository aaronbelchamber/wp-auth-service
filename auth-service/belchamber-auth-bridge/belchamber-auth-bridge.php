<?php
/**
 * Plugin Name: Belchamber Auth Bridge & Session Storage
 * Plugin URI:  https://github.com/aaronbelchamber/wp-auth-service
 * Description: Lightweight WordPress plugin providing custom DB session storage, per-app global (non-PII) data storage, REST API endpoints, rate limiting, and centralized Application Password connection management, logging, and security tools. Part of the wp-auth-service toolkit — more free WordPress tools at tools.belchamber.us.
 * Version:     1.3.0
 * Author:      Aaron Belchamber
 * Author URI:  https://belchamber.us
 * License:     GPLv2 or later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: belchamber-auth-bridge
 */

if (!defined('ABSPATH')) {
    exit; // Exit if accessed directly.
}

define('BELCHAMBER_AUTH_BRIDGE_VERSION', '1.3.0');
define('BELCHAMBER_AUTH_BRIDGE_DB_VERSION', '1.3.0');

/**
 * 1. Reverse Proxy HTTPS Detection
 */
if (
    (!empty($_SERVER['HTTP_X_FORWARDED_PROTO']) && strtolower($_SERVER['HTTP_X_FORWARDED_PROTO']) === 'https') ||
    (!empty($_SERVER['HTTP_X_FORWARDED_SSL']) && strtolower($_SERVER['HTTP_X_FORWARDED_SSL']) === 'on') ||
    (!empty($_SERVER['HTTP_FRONT_END_HTTPS']) && strtolower($_SERVER['HTTP_FRONT_END_HTTPS']) === 'on') ||
    (!empty($_SERVER['HTTP_CF_VISITOR']) && str_contains($_SERVER['HTTP_CF_VISITOR'], 'https'))
) {
    $_SERVER['HTTPS'] = 'on';
}

/**
 * 2. Ensure Application Passwords feature is available regardless of connection type.
 */
add_filter('wp_is_application_passwords_available', '__return_true', 99999);
add_filter('wp_is_application_passwords_available_for_user', '__return_true', 99999);

/**
 * Main Plugin Class
 */
class Belchamber_Auth_Bridge {
    private static $instance = null;

    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        $this->init_hooks();
        Belchamber_Auth_Bridge_Logger::get_instance();
        Belchamber_Auth_Bridge_Security::get_instance();
        if (is_admin()) {
            Belchamber_Auth_Bridge_Admin::get_instance();
        }
    }

    private function init_hooks() {
        register_activation_hook(__FILE__, array('Belchamber_Auth_Bridge_DB', 'activate'));
        add_action('wp_authorize_application_password_request_errors', array($this, 'handle_loopback_and_whitelist_errors'), 99999, 3);
        add_action('rest_api_init', array($this, 'register_rest_routes'));
        // Updating the plugin files alone (without deactivate/reactivate) doesn't
        // re-fire register_activation_hook, so re-run the DB provisioner whenever
        // the stored DB version falls behind — this is what actually creates
        // wp_belchamber_auth_global_data for sites that update in place.
        add_action('admin_init', array('Belchamber_Auth_Bridge_DB', 'maybe_upgrade'));
    }

    /**
     * Handle loopback callback errors and enforce app whitelist if enabled.
     */
    public function handle_loopback_and_whitelist_errors($error, $request, $user) {
        if (!is_wp_error($error)) {
            $error = new WP_Error();
        }

        // Whitelist Check — matches on either app_id (stable, preferred) or app_name
        // (legacy; kept so existing name-based whitelist entries keep working without
        // requiring every admin to re-enter their whitelist as IDs).
        $app_id = !empty($request['app_id']) ? $request['app_id'] : '';
        $app_name = !empty($request['app_name']) ? $request['app_name'] : '';
        $whitelisted = ($app_id !== '' && $this->is_app_whitelisted($app_id))
            || ($app_name !== '' && $this->is_app_whitelisted($app_name));

        if (!$whitelisted) {
            $error->add('app_not_whitelisted', __('This application is not authorized to connect to this WordPress site. Ask your site admin to whitelist its app ID or name in Tools → App Connections → Settings.', 'belchamber-auth-bridge'));
            return;
        }

        if (!$error->has_errors()) {
            return;
        }

        $codes = $error->get_error_codes();
        $scheme_errors = array('invalid_redirect_scheme', 'invalid_redirect_url', 'invalid_redirect_url_format');
        $only_scheme_errors = empty(array_diff($codes, $scheme_errors));
        if (!$only_scheme_errors) {
            return;
        }

        $urls_to_check = array();
        if (!empty($request['success_url'])) {
            $urls_to_check[] = $request['success_url'];
        }
        if (!empty($request['reject_url'])) {
            $urls_to_check[] = $request['reject_url'];
        }

        $loopback_hosts = array('localhost', '127.0.0.1', '[::1]', '::1');
        $all_local = true;
        foreach ($urls_to_check as $url) {
            $host = wp_parse_url($url, PHP_URL_HOST);
            if (!$host || !in_array(strtolower($host), $loopback_hosts, true)) {
                $all_local = false;
                break;
            }
        }

        if ($all_local) {
            foreach ($scheme_errors as $code) {
                $error->remove($code);
            }
        }
    }

    /**
     * Register REST API Endpoints under namespace 'auth-bridge/v1'.
     */
    public function register_rest_routes() {
        register_rest_route('auth-bridge/v1', '/health', array(
            'methods'             => WP_REST_Server::READABLE,
            'callback'            => array($this, 'health_check'),
            'permission_callback' => '__return_true',
            'args'                => array(
                'app_id' => array('required' => false, 'sanitize_callback' => 'sanitize_text_field'),
            ),
        ));

        register_rest_route('auth-bridge/v1', '/global', array(
            array(
                'methods'             => WP_REST_Server::READABLE,
                'callback'            => array($this, 'get_global'),
                'permission_callback' => '__return_true',
                'args'                => array(
                    'app_id' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                    'key'    => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                ),
            ),
            array(
                'methods'             => WP_REST_Server::CREATABLE,
                'callback'            => array($this, 'save_global'),
                'permission_callback' => array($this, 'global_write_permissions_check'),
                'args'                => array(
                    'app_id'  => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                    'key'     => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                    'payload' => array('required' => true),
                ),
            ),
            array(
                'methods'             => WP_REST_Server::DELETABLE,
                'callback'            => array($this, 'delete_global'),
                'permission_callback' => array($this, 'global_write_permissions_check'),
                'args'                => array(
                    'app_id' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                    'key'    => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                ),
            ),
        ));

        register_rest_route('auth-bridge/v1', '/session', array(
            array(
                'methods'             => WP_REST_Server::READABLE,
                'callback'            => array($this, 'get_session'),
                'permission_callback' => array($this, 'permissions_check'),
                'args'                => array(
                    'app_id' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                    'session_key' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                ),
            ),
            array(
                'methods'             => WP_REST_Server::CREATABLE,
                'callback'            => array($this, 'save_session'),
                'permission_callback' => array($this, 'permissions_check'),
                'args'                => array(
                    'app_id' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                    'session_key' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                    'payload' => array('required' => true),
                ),
            ),
            array(
                'methods'             => WP_REST_Server::DELETABLE,
                'callback'            => array($this, 'delete_session'),
                'permission_callback' => array($this, 'permissions_check'),
                'args'                => array(
                    'app_id' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                    'session_key' => array('required' => true, 'sanitize_callback' => 'sanitize_text_field'),
                ),
            ),
        ));
    }

    public function health_check($request) {
        $response = array(
            'status'  => 'active',
            'plugin'  => 'belchamber-auth-bridge',
            'version' => BELCHAMBER_AUTH_BRIDGE_VERSION,
        );

        // Pre-flight check: lets a client verify its app_id is whitelisted
        // *before* attempting the authorize-application.php redirect, instead
        // of only discovering it via a confusing WP-side error page.
        $app_id = $request->get_param('app_id');
        if (!empty($app_id)) {
            $response['app_id_whitelisted'] = $this->is_app_whitelisted($app_id);
        }

        return rest_ensure_response($response);
    }

    public function permissions_check($request) {
        if (!is_user_logged_in()) {
            return new WP_Error('rest_forbidden', __('You must be logged in to perform this operation.', 'belchamber-auth-bridge'), array('status' => 401));
        }
        return true;
    }

    /**
     * Permission callback for writes to /global: requires a logged-in user
     * AND that user must be listed as an owner for the target app_id (see
     * belchamber_auth_bridge_app_owners option) — this is what makes /global writes
     * "the app itself" rather than any authenticated end user.
     */
    public function global_write_permissions_check($request) {
        if (!is_user_logged_in()) {
            return new WP_Error('rest_forbidden', __('You must be logged in to perform this operation.', 'belchamber-auth-bridge'), array('status' => 401));
        }

        $app_id = $request->get_param('app_id');
        if (!$this->is_app_owner($app_id, get_current_user_id())) {
            return new WP_Error(
                'rest_forbidden_owner',
                __('Your account is not authorized to write global data for this app.', 'belchamber-auth-bridge'),
                array('status' => 403)
            );
        }

        return true;
    }

    /**
     * Whether $value (an app_id or app_name) is present in the whitelist
     * setting. Returns true when no whitelist is configured at all — matches
     * the plugin's existing "unrestricted by default" behavior.
     */
    private function is_app_whitelisted($value) {
        $whitelist_setting = get_option('belchamber_auth_bridge_app_whitelist', '');
        if (empty($whitelist_setting)) {
            return true;
        }
        $allowed = array_map('trim', explode(',', strtolower($whitelist_setting)));
        return in_array(strtolower($value), $allowed, true);
    }

    /**
     * Whether $user_id is registered as an owner of $app_id for /global
     * writes, via the belchamber_auth_bridge_app_owners option (app_id => [user_id,...]).
     */
    private function is_app_owner($app_id, $user_id) {
        $owners = get_option('belchamber_auth_bridge_app_owners', array());
        if (!is_array($owners) || empty($app_id) || empty($owners[$app_id])) {
            return false;
        }
        return in_array((int) $user_id, array_map('intval', (array) $owners[$app_id]), true);
    }

    private function client_ip() {
        return !empty($_SERVER['REMOTE_ADDR']) ? sanitize_text_field($_SERVER['REMOTE_ADDR']) : 'unknown';
    }

    public function get_session($request) {
        global $wpdb;
        $user_id = get_current_user_id();
        $app_id = $request->get_param('app_id');
        $session_key = $request->get_param('session_key');

        if (!Belchamber_Auth_Bridge_Security::get_instance()->check_rate_limit("session_get_u{$user_id}_{$app_id}", 120, 60)) {
            return $this->rate_limited_response();
        }

        $table_name = $wpdb->prefix . 'belchamber_auth_sessions';
        $row = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM $table_name WHERE user_id = %d AND app_id = %s AND session_key = %s LIMIT 1",
            $user_id, $app_id, $session_key
        ));

        if (!$row) {
            return new WP_Error('session_not_found', __('Session entry not found.', 'belchamber-auth-bridge'), array('status' => 404));
        }

        Belchamber_Auth_Bridge_Logger::get_instance()->log_event($user_id, $app_id, 'session_read', '', $session_key);

        $payload = json_decode($row->payload, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            $payload = $row->payload;
        }

        return rest_ensure_response(array(
            'id'          => (int)$row->id,
            'user_id'     => (int)$row->user_id,
            'app_id'      => $row->app_id,
            'session_key' => $row->session_key,
            'payload'     => $payload,
            'created_at'  => (int)$row->created_at,
            'updated_at'  => (int)$row->updated_at,
        ));
    }

    public function save_session($request) {
        global $wpdb;
        $user_id = get_current_user_id();
        $app_id = $request->get_param('app_id');
        $session_key = $request->get_param('session_key');
        $payload_raw = $request->get_param('payload');

        if (!Belchamber_Auth_Bridge_Security::get_instance()->check_rate_limit("session_save_u{$user_id}_{$app_id}", 60, 60)) {
            return $this->rate_limited_response();
        }

        if (is_array($payload_raw) || is_object($payload_raw)) {
            $payload_str = wp_json_encode($payload_raw);
        } else {
            $payload_str = (string)$payload_raw;
        }

        $now = time();
        $table_name = $wpdb->prefix . 'belchamber_auth_sessions';

        $existing = $wpdb->get_row($wpdb->prepare(
            "SELECT id, created_at FROM $table_name WHERE user_id = %d AND app_id = %s AND session_key = %s LIMIT 1",
            $user_id, $app_id, $session_key
        ));

        if ($existing) {
            $updated = $wpdb->update(
                $table_name,
                array('payload' => $payload_str, 'updated_at' => $now),
                array('id' => $existing->id),
                array('%s', '%d'),
                array('%d')
            );

            if ($updated === false) {
                return new WP_Error('db_update_error', __('Failed to update session payload.', 'belchamber-auth-bridge'), array('status' => 500));
            }

            Belchamber_Auth_Bridge_Logger::get_instance()->log_event($user_id, $app_id, 'session_write', '', $session_key);

            return rest_ensure_response(array(
                'success' => true, 'action' => 'updated', 'user_id' => $user_id,
                'app_id' => $app_id, 'session_key' => $session_key, 'updated_at' => $now,
            ));
        } else {
            $inserted = $wpdb->insert(
                $table_name,
                array(
                    'user_id' => $user_id, 'app_id' => $app_id,
                    'session_key' => $session_key, 'payload' => $payload_str,
                    'created_at' => $now, 'updated_at' => $now,
                ),
                array('%d', '%s', '%s', '%s', '%d', '%d')
            );

            if (!$inserted) {
                return new WP_Error('db_insert_error', __('Failed to insert session payload.', 'belchamber-auth-bridge'), array('status' => 500));
            }

            Belchamber_Auth_Bridge_Logger::get_instance()->log_event($user_id, $app_id, 'session_write', '', $session_key);

            return rest_ensure_response(array(
                'success' => true, 'action' => 'created', 'user_id' => $user_id,
                'app_id' => $app_id, 'session_key' => $session_key,
                'created_at' => $now, 'updated_at' => $now,
            ));
        }
    }

    public function delete_session($request) {
        global $wpdb;
        $user_id = get_current_user_id();
        $app_id = $request->get_param('app_id');
        $session_key = $request->get_param('session_key');

        if (!Belchamber_Auth_Bridge_Security::get_instance()->check_rate_limit("session_delete_u{$user_id}_{$app_id}", 60, 60)) {
            return $this->rate_limited_response();
        }

        $table_name = $wpdb->prefix . 'belchamber_auth_sessions';
        $deleted = $wpdb->delete(
            $table_name,
            array('user_id' => $user_id, 'app_id' => $app_id, 'session_key' => $session_key),
            array('%d', '%s', '%s')
        );

        if (!$deleted) {
            return new WP_Error('session_not_found', __('Session entry not found or already deleted.', 'belchamber-auth-bridge'), array('status' => 404));
        }

        Belchamber_Auth_Bridge_Logger::get_instance()->log_event($user_id, $app_id, 'session_delete', '', $session_key);

        return rest_ensure_response(array(
            'success' => true, 'action' => 'deleted',
            'app_id' => $app_id, 'session_key' => $session_key,
        ));
    }

    /**
     * Global (per-app_id, not per-user) non-PII data storage — GET is public
     * by design (see plan doc); writes are gated by global_write_permissions_check.
     */
    public function get_global($request) {
        global $wpdb;
        $app_id = $request->get_param('app_id');
        $data_key = $request->get_param('key');

        if (!Belchamber_Auth_Bridge_Security::get_instance()->check_rate_limit("global_get_ip{$this->client_ip()}_{$app_id}", 120, 60)) {
            return $this->rate_limited_response();
        }

        $table_name = $wpdb->prefix . 'belchamber_auth_global_data';
        $row = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM $table_name WHERE app_id = %s AND data_key = %s LIMIT 1",
            $app_id, $data_key
        ));

        if (!$row) {
            return new WP_Error('global_not_found', __('Global data entry not found.', 'belchamber-auth-bridge'), array('status' => 404));
        }

        $payload = json_decode($row->payload, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            $payload = $row->payload;
        }

        return rest_ensure_response(array(
            'app_id'     => $row->app_id,
            'key'        => $row->data_key,
            'payload'    => $payload,
            'updated_at' => (int) $row->updated_at,
        ));
    }

    public function save_global($request) {
        global $wpdb;
        $user_id = get_current_user_id();
        $app_id = $request->get_param('app_id');
        $data_key = $request->get_param('key');
        $payload_raw = $request->get_param('payload');

        if (!Belchamber_Auth_Bridge_Security::get_instance()->check_rate_limit("global_save_u{$user_id}_{$app_id}", 60, 60)) {
            return $this->rate_limited_response();
        }

        $payload_str = (is_array($payload_raw) || is_object($payload_raw)) ? wp_json_encode($payload_raw) : (string) $payload_raw;
        $now = time();
        $table_name = $wpdb->prefix . 'belchamber_auth_global_data';

        $existing = $wpdb->get_row($wpdb->prepare(
            "SELECT id FROM $table_name WHERE app_id = %s AND data_key = %s LIMIT 1",
            $app_id, $data_key
        ));

        if ($existing) {
            $updated = $wpdb->update(
                $table_name,
                array('payload' => $payload_str, 'updated_by_user_id' => $user_id, 'updated_at' => $now),
                array('id' => $existing->id),
                array('%s', '%d', '%d'),
                array('%d')
            );

            if ($updated === false) {
                return new WP_Error('db_update_error', __('Failed to update global data.', 'belchamber-auth-bridge'), array('status' => 500));
            }

            return rest_ensure_response(array(
                'success' => true, 'action' => 'updated',
                'app_id' => $app_id, 'key' => $data_key, 'updated_at' => $now,
            ));
        }

        $inserted = $wpdb->insert(
            $table_name,
            array(
                'app_id' => $app_id, 'data_key' => $data_key, 'payload' => $payload_str,
                'updated_by_user_id' => $user_id, 'created_at' => $now, 'updated_at' => $now,
            ),
            array('%s', '%s', '%s', '%d', '%d', '%d')
        );

        if (!$inserted) {
            return new WP_Error('db_insert_error', __('Failed to insert global data.', 'belchamber-auth-bridge'), array('status' => 500));
        }

        return rest_ensure_response(array(
            'success' => true, 'action' => 'created',
            'app_id' => $app_id, 'key' => $data_key, 'created_at' => $now, 'updated_at' => $now,
        ));
    }

    public function delete_global($request) {
        global $wpdb;
        $user_id = get_current_user_id();
        $app_id = $request->get_param('app_id');
        $data_key = $request->get_param('key');

        if (!Belchamber_Auth_Bridge_Security::get_instance()->check_rate_limit("global_delete_u{$user_id}_{$app_id}", 60, 60)) {
            return $this->rate_limited_response();
        }

        $table_name = $wpdb->prefix . 'belchamber_auth_global_data';
        $deleted = $wpdb->delete(
            $table_name,
            array('app_id' => $app_id, 'data_key' => $data_key),
            array('%s', '%s')
        );

        if (!$deleted) {
            return new WP_Error('global_not_found', __('Global data entry not found or already deleted.', 'belchamber-auth-bridge'), array('status' => 404));
        }

        return rest_ensure_response(array(
            'success' => true, 'action' => 'deleted',
            'app_id' => $app_id, 'key' => $data_key,
        ));
    }

    private function rate_limited_response() {
        header('Retry-After: 60');
        return new WP_Error('rate_limited', __('Too many requests. Please slow down.', 'belchamber-auth-bridge'), array('status' => 429));
    }
}

/**
 * Database Provisioner Class
 */
class Belchamber_Auth_Bridge_DB {
    public static function maybe_upgrade() {
        if (get_option('belchamber_auth_bridge_db_version') !== BELCHAMBER_AUTH_BRIDGE_DB_VERSION) {
            self::activate();
        }
    }

    /**
     * One-time migration for sites upgrading from the old "wp-app-bridge"
     * plugin slug (pre-1.3.0 rename). Renames the legacy tables in place
     * (preserving session/whitelist data instead of starting fresh under
     * the new names) and carries over the old option values. Safe to run
     * repeatedly — every step is a no-op once migrated.
     */
    private static function migrate_from_legacy_wp_app_bridge() {
        global $wpdb;

        $table_renames = array(
            $wpdb->prefix . 'app_sessions'    => $wpdb->prefix . 'belchamber_auth_sessions',
            $wpdb->prefix . 'app_global_data' => $wpdb->prefix . 'belchamber_auth_global_data',
            $wpdb->prefix . 'app_auth_logs'   => $wpdb->prefix . 'belchamber_auth_logs',
        );
        foreach ($table_renames as $old_table => $new_table) {
            $old_exists = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $old_table));
            $new_exists = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $new_table));
            if ($old_exists && !$new_exists) {
                $wpdb->query("RENAME TABLE `$old_table` TO `$new_table`");
            }
        }

        $option_renames = array(
            'wp_app_bridge_db_version'    => 'belchamber_auth_bridge_db_version',
            'wp_app_bridge_app_whitelist' => 'belchamber_auth_bridge_app_whitelist',
            'wp_app_bridge_app_owners'    => 'belchamber_auth_bridge_app_owners',
            'wp_app_bridge_ttl_days'      => 'belchamber_auth_bridge_ttl_days',
            'wp_app_bridge_notify_admin'  => 'belchamber_auth_bridge_notify_admin',
        );
        foreach ($option_renames as $old_key => $new_key) {
            $old_val = get_option($old_key, null);
            if ($old_val !== null && get_option($new_key, null) === null) {
                update_option($new_key, $old_val);
            }
        }

        // Deactivate the old plugin so WordPress doesn't show two entries
        // for what is now the same plugin under a new name.
        if (!function_exists('is_plugin_active')) {
            require_once(ABSPATH . 'wp-admin/includes/plugin.php');
        }
        $legacy_plugin_file = 'wp-app-bridge/wp-app-bridge.php';
        if (is_plugin_active($legacy_plugin_file)) {
            deactivate_plugins($legacy_plugin_file);
        }
    }

    public static function activate() {
        global $wpdb;

        self::migrate_from_legacy_wp_app_bridge();

        $charset_collate = $wpdb->get_charset_collate();
        require_once(ABSPATH . 'wp-admin/includes/upgrade.php');

        // Sessions Table
        $table_sessions = $wpdb->prefix . 'belchamber_auth_sessions';
        $sql_sessions = "CREATE TABLE $table_sessions (
            id bigint(20) NOT NULL AUTO_INCREMENT,
            user_id bigint(20) NOT NULL,
            app_id varchar(64) NOT NULL,
            session_key varchar(128) NOT NULL,
            payload longtext NOT NULL,
            created_at bigint(20) NOT NULL,
            updated_at bigint(20) NOT NULL,
            PRIMARY KEY  (id),
            KEY user_app_session (user_id, app_id, session_key)
        ) $charset_collate;";
        dbDelta($sql_sessions);

        // Global (per-app_id, not per-user) non-PII data table
        $table_global = $wpdb->prefix . 'belchamber_auth_global_data';
        $sql_global = "CREATE TABLE $table_global (
            id bigint(20) NOT NULL AUTO_INCREMENT,
            app_id varchar(64) NOT NULL,
            data_key varchar(128) NOT NULL,
            payload longtext NOT NULL,
            updated_by_user_id bigint(20) NOT NULL,
            created_at bigint(20) NOT NULL,
            updated_at bigint(20) NOT NULL,
            PRIMARY KEY  (id),
            UNIQUE KEY app_data_key (app_id, data_key)
        ) $charset_collate;";
        dbDelta($sql_global);

        // Audit Logs Table with admin_user_id tracking
        $table_logs = $wpdb->prefix . 'belchamber_auth_logs';
        $sql_logs = "CREATE TABLE $table_logs (
            id bigint(20) NOT NULL AUTO_INCREMENT,
            user_id bigint(20) NOT NULL,
            admin_user_id bigint(20) DEFAULT 0,
            app_name varchar(191) NOT NULL,
            app_id varchar(64) DEFAULT '',
            uuid varchar(64) DEFAULT '',
            event_type varchar(32) NOT NULL,
            ip_address varchar(45) NOT NULL,
            user_agent text,
            created_at bigint(20) NOT NULL,
            PRIMARY KEY  (id),
            KEY user_app (user_id, app_name),
            KEY admin_user (admin_user_id)
        ) $charset_collate;";
        dbDelta($sql_logs);

        update_option('belchamber_auth_bridge_db_version', BELCHAMBER_AUTH_BRIDGE_DB_VERSION);
    }
}

/**
 * Audit Logger Class
 */
class Belchamber_Auth_Bridge_Logger {
    private static $instance = null;

    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_action('wp_create_application_password', array($this, 'on_password_created'), 10, 4);
        add_action('wp_delete_application_password', array($this, 'on_password_deleted'), 10, 2);
        add_action('determine_current_user', array($this, 'track_application_password_usage'), 20);
    }

    public function log_event($user_id, $app_name, $event_type, $uuid = '', $app_id = '', $admin_user_id = 0) {
        global $wpdb;
        $table_name = $wpdb->prefix . 'belchamber_auth_logs';
        $ip = !empty($_SERVER['REMOTE_ADDR']) ? sanitize_text_field($_SERVER['REMOTE_ADDR']) : 'unknown';
        $ua = !empty($_SERVER['HTTP_USER_AGENT']) ? sanitize_text_field($_SERVER['HTTP_USER_AGENT']) : '';

        // If admin_user_id is not explicitly passed, detect current logged in admin user
        if ($admin_user_id === 0 && is_user_logged_in() && current_user_can('manage_options')) {
            $admin_user_id = get_current_user_id();
        }

        $wpdb->insert(
            $table_name,
            array(
                'user_id'       => (int)$user_id,
                'admin_user_id' => (int)$admin_user_id,
                'app_name'      => sanitize_text_field($app_name),
                'app_id'        => sanitize_text_field($app_id),
                'uuid'          => sanitize_text_field($uuid),
                'event_type'    => sanitize_text_field($event_type),
                'ip_address'    => $ip,
                'user_agent'    => $ua,
                'created_at'    => time(),
            ),
            array('%d', '%d', '%s', '%s', '%s', '%s', '%s', '%s', '%d')
        );
    }

    public function on_password_created($user_id, $new_item, $new_password, $args) {
        $app_name = !empty($new_item['name']) ? $new_item['name'] : 'Unknown App';
        $uuid = !empty($new_item['uuid']) ? $new_item['uuid'] : '';
        $app_id = !empty($new_item['app_id']) ? $new_item['app_id'] : '';
        $this->log_event($user_id, $app_name, 'created', $uuid, $app_id);
    }

    public function on_password_deleted($user_id, $item) {
        $app_name = !empty($item['name']) ? $item['name'] : 'Unknown App';
        $uuid = !empty($item['uuid']) ? $item['uuid'] : '';
        $app_id = !empty($item['app_id']) ? $item['app_id'] : '';
        $this->log_event($user_id, $app_name, 'revoked', $uuid, $app_id);
    }

    public function track_application_password_usage($user_id) {
        if (!empty($user_id) && defined('REST_REQUEST') && REST_REQUEST) {
            // Check if authenticated via application password
            if (!empty($_SERVER['PHP_AUTH_USER']) && !empty($_SERVER['PHP_AUTH_PW'])) {
                $passwords = WP_Application_Passwords::get_user_application_passwords($user_id);
                foreach ($passwords as $p) {
                    if (wp_check_password($_SERVER['PHP_AUTH_PW'], $p['password'])) {
                        // Rate-limit logging usage to once per 5 minutes per uuid to avoid DB spam
                        $transient_key = 'belchamber_auth_bridge_log_use_' . $p['uuid'];
                        if (!get_transient($transient_key)) {
                            set_transient($transient_key, true, 300);
                            $this->log_event($user_id, $p['name'], 'api_access', $p['uuid'], isset($p['app_id']) ? $p['app_id'] : '');
                        }
                        break;
                    }
                }
            }
        }
        return $user_id;
    }
}

/**
 * Security & Expiration Engine
 */
class Belchamber_Auth_Bridge_Security {
    private static $instance = null;

    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_action('wp_create_application_password', array($this, 'notify_admin_on_high_privilege_auth'), 10, 4);
        add_action('belchamber_auth_bridge_ttl_cleanup', array($this, 'run_ttl_cleanup'));

        if (!wp_next_scheduled('belchamber_auth_bridge_ttl_cleanup')) {
            wp_schedule_event(time(), 'daily', 'belchamber_auth_bridge_ttl_cleanup');
        }
    }

    public function notify_admin_on_high_privilege_auth($user_id, $new_item, $new_password, $args) {
        $enabled = get_option('belchamber_auth_bridge_notify_admin', '1');
        if ('1' !== $enabled) {
            return;
        }

        $user = get_userdata($user_id);
        if ($user && in_array('administrator', (array)$user->roles, true)) {
            $admin_email = get_option('admin_email');
            $app_name = !empty($new_item['name']) ? $new_item['name'] : 'Unknown App';
            $subject = sprintf('[Security Alert] New Application Authorized for Admin on %s', get_bloginfo('name'));
            $message = sprintf(
                "An external application password has been authorized for Administrator account '%s'.\n\nApplication Name: %s\nTime: %s\nIP Address: %s\n\nIf you did not authorize this application, please visit WP Admin > Tools > App Connections immediately to revoke access.",
                $user->user_login,
                $app_name,
                current_time('mysql'),
                !empty($_SERVER['REMOTE_ADDR']) ? sanitize_text_field($_SERVER['REMOTE_ADDR']) : 'Unknown'
            );
            wp_mail($admin_email, $subject, $message);
        }
    }

    /**
     * Simple fixed-window rate limiter, reusing the same transient pattern
     * already used for audit-log-usage dedup. This is a backstop against
     * misbehaving clients, not a tight budget — defaults passed in by
     * callers aim for ~1 req/sec sustained with a small burst allowance.
     * Returns false once $bucket_key has been hit $max times within
     * $window_seconds.
     */
    public function check_rate_limit($bucket_key, $max, $window_seconds) {
        $key = 'belchamber_auth_bridge_rl_' . md5($bucket_key);
        $count = (int) get_transient($key);

        if ($count >= $max) {
            return false;
        }

        set_transient($key, $count + 1, $window_seconds);
        return true;
    }

    public function run_ttl_cleanup() {
        $ttl_days = (int)get_option('belchamber_auth_bridge_ttl_days', 0);
        if ($ttl_days <= 0) {
            return; // Disabled
        }

        $threshold = time() - ($ttl_days * 86400);
        $users = get_users(array('fields' => 'ID'));

        foreach ($users as $user_id) {
            $passwords = WP_Application_Passwords::get_user_application_passwords($user_id);
            if (empty($passwords)) {
                continue;
            }

            foreach ($passwords as $p) {
                $last_activity = !empty($p['last_used']) ? (int)$p['last_used'] : (int)$p['created'];
                if ($last_activity < $threshold) {
                    WP_Application_Passwords::delete_application_password($user_id, $p['uuid']);
                    Belchamber_Auth_Bridge_Logger::get_instance()->log_event(
                        $user_id,
                        $p['name'],
                        'auto_expired',
                        $p['uuid'],
                        isset($p['app_id']) ? $p['app_id'] : ''
                    );
                }
            }
        }
    }
}

/**
 * Admin Dashboard UI & Management Class
 */
class Belchamber_Auth_Bridge_Admin {
    private static $instance = null;

    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_action('admin_menu', array($this, 'register_admin_menu'));
        add_action('admin_post_belchamber_auth_bridge_revoke', array($this, 'handle_revoke_action'));
        add_action('admin_post_belchamber_auth_bridge_purge_sessions', array($this, 'handle_purge_sessions_action'));
        add_action('admin_post_belchamber_auth_bridge_kill_switch', array($this, 'handle_kill_switch_action'));
        add_action('admin_post_belchamber_auth_bridge_save_settings', array($this, 'handle_save_settings_action'));
    }

    public function register_admin_menu() {
        add_management_page(
            __('App Connections', 'belchamber-auth-bridge'),
            __('App Connections', 'belchamber-auth-bridge'),
            'manage_options',
            'belchamber-auth-bridge-connections',
            array($this, 'render_admin_page')
        );
    }

    public function render_admin_page() {
        if (!current_user_can('manage_options')) {
            wp_die(__('You do not have sufficient permissions to access this page.', 'belchamber-auth-bridge'));
        }

        $active_tab = isset($_GET['tab']) ? sanitize_text_field($_GET['tab']) : 'connections';
        ?>
        <div class="wrap">
            <h1 class="wp-heading-inline">
                <span class="dashicons dashicons-rest-api" style="font-size:30px; width:30px; height:30px; margin-right:8px;"></span>
                <?php _e('Application Connections & Auth Service', 'belchamber-auth-bridge'); ?>
            </h1>
            <hr class="wp-header-end">

            <?php if (isset($_GET['message'])) : ?>
                <div class="notice notice-success is-dismissible">
                    <p><?php echo esc_html(sanitize_text_field($_GET['message'])); ?></p>
                </div>
            <?php endif; ?>

            <nav class="nav-tab-wrapper">
                <a href="?page=belchamber-auth-bridge-connections&tab=connections" class="nav-tab <?php echo $active_tab === 'connections' ? 'nav-tab-active' : ''; ?>">
                    <?php _e('Active Connections', 'belchamber-auth-bridge'); ?>
                </a>
                <a href="?page=belchamber-auth-bridge-connections&tab=logs" class="nav-tab <?php echo $active_tab === 'logs' ? 'nav-tab-active' : ''; ?>">
                    <?php _e('Audit Logs', 'belchamber-auth-bridge'); ?>
                </a>
                <a href="?page=belchamber-auth-bridge-connections&tab=settings" class="nav-tab <?php echo $active_tab === 'settings' ? 'nav-tab-active' : ''; ?>">
                    <?php _e('Security & Settings', 'belchamber-auth-bridge'); ?>
                </a>
            </nav>

            <div class="tab-content" style="margin-top:20px;">
                <?php
                if ($active_tab === 'logs') {
                    $this->render_logs_tab();
                } elseif ($active_tab === 'settings') {
                    $this->render_settings_tab();
                } else {
                    $this->render_connections_tab();
                }
                ?>
            </div>

            <p style="color:#646970; margin-top:24px;">
                <?php _e('Built by', 'belchamber-auth-bridge'); ?> <a href="https://belchamber.us" target="_blank" rel="noopener noreferrer">Aaron Belchamber</a> &mdash;
                <?php _e('more free WordPress tools at', 'belchamber-auth-bridge'); ?> <a href="https://tools.belchamber.us" target="_blank" rel="noopener noreferrer">tools.belchamber.us</a>.
            </p>
        </div>
        <?php
    }

    private function render_connections_tab() {
        global $wpdb;
        $users = get_users();
        $all_connections = array();

        foreach ($users as $user) {
            $passwords = WP_Application_Passwords::get_user_application_passwords($user->ID);
            if (!empty($passwords)) {
                foreach ($passwords as $p) {
                    $all_connections[] = array(
                        'user_id'       => $user->ID,
                        'user_login'    => $user->user_login,
                        'user_email'    => $user->user_email,
                        'uuid'          => $p['uuid'],
                        'app_name'      => $p['name'],
                        'app_id'        => isset($p['app_id']) ? $p['app_id'] : '',
                        'created'       => $p['created'],
                        'last_used'     => $p['last_used'],
                        'last_ip'       => $p['last_ip'],
                    );
                }
            }
        }
        ?>
        <div class="card" style="max-width:100%; margin-bottom:20px; padding:15px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h2 style="margin-top:0;"><?php _e('Active Authorized Applications Across All Users', 'belchamber-auth-bridge'); ?></h2>
                    <p class="description"><?php _e('Monitor external applications currently authorized via WordPress Application Passwords. You can revoke access or purge stored session data for any application connection.', 'belchamber-auth-bridge'); ?></p>
                </div>
                <div>
                    <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>" onsubmit="return confirm('WARNING: Are you sure you want to revoke ALL application connections site-wide? Existing app sessions will be terminated immediately.');">
                        <?php wp_nonce_field('belchamber_auth_bridge_kill_switch_action', 'belchamber_auth_bridge_nonce'); ?>
                        <input type="hidden" name="action" value="belchamber_auth_bridge_kill_switch">
                        <button type="submit" class="button button-link-delete" style="color:#d63638; text-decoration:none;">
                            <span class="dashicons dashicons-shield-alt" style="vertical-align:middle;"></span>
                            <?php _e('Emergency Revoke All Connections', 'belchamber-auth-bridge'); ?>
                        </button>
                    </form>
                </div>
            </div>
        </div>

        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th scope="col"><?php _e('User', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('Application Name', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('App ID / UUID', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('Created Date', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('Last Activity', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('Remote Sessions', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col" style="text-align:right;"><?php _e('Actions', 'belchamber-auth-bridge'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($all_connections)) : ?>
                    <tr>
                        <td colspan="7"><?php _e('No active application connections found.', 'belchamber-auth-bridge'); ?></td>
                    </tr>
                <?php else : ?>
                    <?php foreach ($all_connections as $conn) :
                        $table_sessions = $wpdb->prefix . 'belchamber_auth_sessions';
                        $session_count = (int)$wpdb->get_var($wpdb->prepare(
                            "SELECT COUNT(*) FROM $table_sessions WHERE user_id = %d AND (app_id = %s OR app_id = %s)",
                            $conn['user_id'], $conn['app_name'], $conn['app_id']
                        ));
                    ?>
                        <tr>
                            <td>
                                <strong><?php echo esc_html($conn['user_login']); ?></strong><br>
                                <span class="description"><?php echo esc_html($conn['user_email']); ?></span>
                            </td>
                            <td>
                                <strong><span class="dashicons dashicons-format-aside" style="vertical-align:middle;"></span> <?php echo esc_html($conn['app_name']); ?></strong>
                            </td>
                            <td>
                                <code><?php echo esc_html(substr($conn['uuid'], 0, 13) . '...'); ?></code>
                            </td>
                            <td><?php echo esc_html(date_i18n(get_option('date_format') . ' ' . get_option('time_format'), $conn['created'])); ?></td>
                            <td>
                                <?php if (!empty($conn['last_used'])) : ?>
                                    <?php echo esc_html(human_time_diff($conn['last_used'], time())) . ' ' . __('ago', 'belchamber-auth-bridge'); ?>
                                    <?php if (!empty($conn['last_ip'])) : ?>
                                        <br><span class="description">IP: <?php echo esc_html($conn['last_ip']); ?></span>
                                    <?php endif; ?>
                                <?php else : ?>
                                    <span class="description"><?php _e('Never used', 'belchamber-auth-bridge'); ?></span>
                                <?php endif; ?>
                            </td>
                            <td>
                                <span class="badge" style="background:#f0f0f1; padding:3px 8px; border-radius:10px; font-weight:600;">
                                    <?php echo sprintf(_n('%d Session', '%d Sessions', $session_count, 'belchamber-auth-bridge'), $session_count); ?>
                                </span>
                                <?php if ($session_count > 0) :
                                    $table_sessions = $wpdb->prefix . 'belchamber_auth_sessions';
                                    $session_rows = $wpdb->get_results($wpdb->prepare(
                                        "SELECT id, app_id, session_key, payload, updated_at FROM $table_sessions WHERE user_id = %d AND (app_id = %s OR app_id = %s) ORDER BY updated_at DESC LIMIT 10",
                                        $conn['user_id'], $conn['app_name'], $conn['app_id']
                                    ));
                                    $json_data = esc_attr(wp_json_encode($session_rows));
                                ?>
                                    <br><button type="button" class="button button-small" style="margin-top:4px; font-size:11px;" onclick='wpAuthBridgeViewData(<?php echo $json_data; ?>)'>
                                        <span class="dashicons dashicons-visibility" style="font-size:14px; vertical-align:middle;"></span> <?php _e('View Data', 'belchamber-auth-bridge'); ?>
                                    </button>
                                <?php endif; ?>
                            </td>
                            <td style="text-align:right;">
                                <div style="display:flex; justify-content:flex-end; gap:8px;">
                                    <?php if ($session_count > 0) : ?>
                                        <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
                                            <?php wp_nonce_field('belchamber_auth_bridge_purge_sessions_action', 'belchamber_auth_bridge_nonce'); ?>
                                            <input type="hidden" name="action" value="belchamber_auth_bridge_purge_sessions">
                                            <input type="hidden" name="user_id" value="<?php echo esc_attr($conn['user_id']); ?>">
                                            <input type="hidden" name="app_name" value="<?php echo esc_attr($conn['app_name']); ?>">
                                            <input type="hidden" name="app_id" value="<?php echo esc_attr($conn['app_id']); ?>">
                                            <button type="submit" class="button button-secondary button-small">
                                                <?php _e('Clear Sessions', 'belchamber-auth-bridge'); ?>
                                            </button>
                                        </form>
                                    <?php endif; ?>

                                    <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>" onsubmit="return confirm('Are you sure you want to revoke access for this application?');">
                                        <?php wp_nonce_field('belchamber_auth_bridge_revoke_action', 'belchamber_auth_bridge_nonce'); ?>
                                        <input type="hidden" name="action" value="belchamber_auth_bridge_revoke">
                                        <input type="hidden" name="user_id" value="<?php echo esc_attr($conn['user_id']); ?>">
                                        <input type="hidden" name="uuid" value="<?php echo esc_attr($conn['uuid']); ?>">
                                        <button type="submit" class="button button-link-delete button-small" style="color:#d63638;">
                                            <?php _e('Revoke', 'belchamber-auth-bridge'); ?>
                                        </button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>
            </tbody>
        </table>

        <!-- Payload Inspector Modal -->
        <div id="belchamber-auth-bridge-modal" style="display:none; position:fixed; z-index:99999; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.6); align-items:center; justify-content:center;">
            <div style="background:#fff; width:90%; max-width:650px; border-radius:8px; padding:20px; box-shadow:0 10px 25px rgba(0,0,0,0.3); max-height:80vh; overflow-y:auto;">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ddd; padding-bottom:10px; margin-bottom:15px;">
                    <h3 style="margin:0; font-size:18px;"><?php _e('Stored Session Payloads', 'belchamber-auth-bridge'); ?></h3>
                    <button type="button" onclick="document.getElementById('belchamber-auth-bridge-modal').style.display='none';" style="background:none; border:none; font-size:20px; cursor:pointer;">&times;</button>
                </div>
                <div id="belchamber-auth-bridge-modal-content"></div>
            </div>
        </div>

        <script>
            function wpAuthBridgeViewData(sessions) {
                var container = document.getElementById('belchamber-auth-bridge-modal-content');
                if (!sessions || !sessions.length) {
                    container.innerHTML = '<p><?php _e('No session data found.', 'belchamber-auth-bridge'); ?></p>';
                } else {
                    var html = '';
                    sessions.forEach(function(s) {
                        var formatted = s.payload;
                        try {
                            formatted = JSON.stringify(JSON.parse(s.payload), null, 2);
                        } catch(e){}
                        html += '<div style="margin-bottom:15px; border:1px solid #e2e8f0; border-radius:6px; padding:12px; background:#f8fafc;">';
                        html += '<div style="font-weight:600; color:#1e293b; margin-bottom:6px;">Key: <code>' + s.session_key + '</code> (App: ' + s.app_id + ')</div>';
                        html += '<pre style="background:#0f172a; color:#f8fafc; padding:10px; border-radius:4px; font-size:12px; overflow-x:auto; margin:0;">' + formatted + '</pre>';
                        html += '</div>';
                    });
                    container.innerHTML = html;
                }
                document.getElementById('belchamber-auth-bridge-modal').style.display = 'flex';
            }
        </script>
        <?php
    }

    private function render_logs_tab() {
        global $wpdb;
        $table_logs = $wpdb->prefix . 'belchamber_auth_logs';
        $logs = $wpdb->get_results("SELECT l.*, u1.user_login as target_login, u2.user_login as admin_login FROM $table_logs l LEFT JOIN {$wpdb->users} u1 ON l.user_id = u1.ID LEFT JOIN {$wpdb->users} u2 ON l.admin_user_id = u2.ID ORDER BY l.created_at DESC LIMIT 100");
        ?>
        <h2><?php _e('Application Authorization Audit Trail', 'belchamber-auth-bridge'); ?></h2>
        <p class="description"><?php _e('Recent connection events including authorization creation, API activity, auto-expirations, and admin management actions.', 'belchamber-auth-bridge'); ?></p>

        <table class="wp-list-table widefat fixed striped" style="margin-top:15px;">
            <thead>
                <tr>
                    <th scope="col"><?php _e('Timestamp', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('Target User ID', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('Performed By (Admin User ID)', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('Application Name', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('Event Type', 'belchamber-auth-bridge'); ?></th>
                    <th scope="col"><?php _e('IP Address', 'belchamber-auth-bridge'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($logs)) : ?>
                    <tr>
                        <td colspan="6"><?php _e('No log entries recorded yet.', 'belchamber-auth-bridge'); ?></td>
                    </tr>
                <?php else : ?>
                    <?php foreach ($logs as $log) :
                        $badge_style = 'background:#2271b1; color:#fff;';
                        if ($log->event_type === 'created') {
                            $badge_style = 'background:#00a32a; color:#fff;';
                        } elseif (str_contains($log->event_type, 'revoked') || str_contains($log->event_type, 'kill_switch')) {
                            $badge_style = 'background:#d63638; color:#fff;';
                        } elseif ($log->event_type === 'auto_expired') {
                            $badge_style = 'background:#dba617; color:#fff;';
                        } elseif (str_contains($log->event_type, 'admin_')) {
                            $badge_style = 'background:#82878c; color:#fff;';
                        }

                        $admin_display = 'System / Self';
                        if (!empty($log->admin_user_id)) {
                            $admin_display = !empty($log->admin_login) ? sprintf('Admin ID #%d (%s)', $log->admin_user_id, $log->admin_login) : sprintf('Admin ID #%d', $log->admin_user_id);
                        }
                    ?>
                        <tr>
                            <td><?php echo esc_html(date_i18n(get_option('date_format') . ' ' . get_option('time_format'), $log->created_at)); ?></td>
                            <td><code>User ID #<?php echo esc_html($log->user_id); ?></code></td>
                            <td><strong><?php echo esc_html($admin_display); ?></strong></td>
                            <td><?php echo esc_html($log->app_name); ?></td>
                            <td>
                                <span style="<?php echo esc_attr($badge_style); ?> padding:2px 8px; border-radius:4px; font-size:11px; text-transform:uppercase; font-weight:600;">
                                    <?php echo esc_html($log->event_type); ?>
                                </span>
                            </td>
                            <td><code><?php echo esc_html($log->ip_address); ?></code></td>
                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>
            </tbody>
        </table>
        <?php
    }

    private function render_settings_tab() {
        $ttl_days = (int)get_option('belchamber_auth_bridge_ttl_days', 0);
        $notify_admin = get_option('belchamber_auth_bridge_notify_admin', '1');
        $whitelist = get_option('belchamber_auth_bridge_app_whitelist', '');
        $owners = get_option('belchamber_auth_bridge_app_owners', array());
        $owners_text = '';
        if (is_array($owners)) {
            $lines = array();
            foreach ($owners as $app_id => $user_ids) {
                $lines[] = $app_id . ' = ' . implode(',', array_map('intval', (array) $user_ids));
            }
            $owners_text = implode("\n", $lines);
        }
        ?>
        <h2><?php _e('Security & Auth Bridge Settings', 'belchamber-auth-bridge'); ?></h2>
        <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>" style="max-width:700px; margin-top:20px;">
            <?php wp_nonce_field('belchamber_auth_bridge_save_settings_action', 'belchamber_auth_bridge_nonce'); ?>
            <input type="hidden" name="action" value="belchamber_auth_bridge_save_settings">

            <table class="form-table">
                <tr>
                    <th scope="row"><label for="ttl_days"><?php _e('Auto-Revoke Inactive Apps (TTL)', 'belchamber-auth-bridge'); ?></label></th>
                    <td>
                        <select name="ttl_days" id="ttl_days">
                            <option value="0" <?php selected($ttl_days, 0); ?>><?php _e('Disabled (Never Auto-Revoke)', 'belchamber-auth-bridge'); ?></option>
                            <option value="30" <?php selected($ttl_days, 30); ?>><?php _e('30 Days of Inactivity', 'belchamber-auth-bridge'); ?></option>
                            <option value="60" <?php selected($ttl_days, 60); ?>><?php _e('60 Days of Inactivity', 'belchamber-auth-bridge'); ?></option>
                            <option value="90" <?php selected($ttl_days, 90); ?>><?php _e('90 Days of Inactivity', 'belchamber-auth-bridge'); ?></option>
                        </select>
                        <p class="description"><?php _e('Automatically revoke application passwords that have not been used within the specified timeframe.', 'belchamber-auth-bridge'); ?></p>
                    </td>
                </tr>
                <tr>
                    <th scope="row"><?php _e('Admin Email Alerts', 'belchamber-auth-bridge'); ?></th>
                    <td>
                        <label for="notify_admin">
                            <input type="checkbox" name="notify_admin" id="notify_admin" value="1" <?php checked($notify_admin, '1'); ?>>
                            <?php _e('Send email alert to site admin when an Administrator authorizes a new external app', 'belchamber-auth-bridge'); ?>
                        </label>
                    </td>
                </tr>
                <tr>
                    <th scope="row"><label for="app_whitelist"><?php _e('Allowed Applications Whitelist', 'belchamber-auth-bridge'); ?></label></th>
                    <td>
                        <input type="text" name="app_whitelist" id="app_whitelist" class="large-text" value="<?php echo esc_attr($whitelist); ?>" placeholder="e.g. fun-activities-app, My Next.js App, Internal CLI">
                        <p class="description"><?php _e('Comma-separated list of approved app IDs (preferred, stable — e.g. "fun-activities-app") and/or app display names (legacy). An app is allowed if either its app_id or its app_name matches an entry here. Leave blank to allow any application.', 'belchamber-auth-bridge'); ?></p>
                    </td>
                </tr>
                <tr>
                    <th scope="row"><label for="app_owners"><?php _e('Global App Data Owners', 'belchamber-auth-bridge'); ?></label></th>
                    <td>
                        <textarea name="app_owners" id="app_owners" class="large-text code" rows="4" placeholder="fun-activities-app = 2&#10;fun-activities-app = 2,5"><?php echo esc_textarea($owners_text); ?></textarea>
                        <p class="description"><?php _e('One line per app: "app_id = user_id[,user_id...]". Only these WordPress user IDs may write to /auth-bridge/v1/global (POST/DELETE) for that app_id — reads are public. Recommended: use a dedicated low-privilege service account\'s user ID here, not a personal admin account.', 'belchamber-auth-bridge'); ?></p>
                    </td>
                </tr>
            </table>

            <?php submit_button(__('Save Settings', 'belchamber-auth-bridge')); ?>
        </form>
        <?php
    }

    public function handle_revoke_action() {
        if (!current_user_can('manage_options') || !check_admin_referer('belchamber_auth_bridge_revoke_action', 'belchamber_auth_bridge_nonce')) {
            wp_die(__('Security check failed.', 'belchamber-auth-bridge'));
        }

        $user_id = isset($_POST['user_id']) ? (int)$_POST['user_id'] : 0;
        $uuid = isset($_POST['uuid']) ? sanitize_text_field($_POST['uuid']) : '';
        $admin_user_id = get_current_user_id();

        if ($user_id > 0 && !empty($uuid)) {
            WP_Application_Passwords::delete_application_password($user_id, $uuid);
            Belchamber_Auth_Bridge_Logger::get_instance()->log_event($user_id, 'App Connection', 'admin_revoke', $uuid, '', $admin_user_id);
            $msg = __('Application connection successfully revoked.', 'belchamber-auth-bridge');
        } else {
            $msg = __('Invalid parameters for revocation.', 'belchamber-auth-bridge');
        }

        wp_safe_redirect(admin_url('tools.php?page=belchamber-auth-bridge-connections&tab=connections&message=' . urlencode($msg)));
        exit;
    }

    public function handle_purge_sessions_action() {
        if (!current_user_can('manage_options') || !check_admin_referer('belchamber_auth_bridge_purge_sessions_action', 'belchamber_auth_bridge_nonce')) {
            wp_die(__('Security check failed.', 'belchamber-auth-bridge'));
        }

        global $wpdb;
        $user_id = isset($_POST['user_id']) ? (int)$_POST['user_id'] : 0;
        $app_name = isset($_POST['app_name']) ? sanitize_text_field($_POST['app_name']) : '';
        $app_id = isset($_POST['app_id']) ? sanitize_text_field($_POST['app_id']) : '';
        $admin_user_id = get_current_user_id();

        $table_sessions = $wpdb->prefix . 'belchamber_auth_sessions';
        $deleted = $wpdb->query($wpdb->prepare(
            "DELETE FROM $table_sessions WHERE user_id = %d AND (app_id = %s OR app_id = %s)",
            $user_id, $app_name, $app_id
        ));

        Belchamber_Auth_Bridge_Logger::get_instance()->log_event($user_id, $app_name, 'admin_purge_sessions', '', $app_id, $admin_user_id);

        $msg = sprintf(__('Cleared %d remote session records.', 'belchamber-auth-bridge'), (int)$deleted);
        wp_safe_redirect(admin_url('tools.php?page=belchamber-auth-bridge-connections&tab=connections&message=' . urlencode($msg)));
        exit;
    }

    public function handle_kill_switch_action() {
        if (!current_user_can('manage_options') || !check_admin_referer('belchamber_auth_bridge_kill_switch_action', 'belchamber_auth_bridge_nonce')) {
            wp_die(__('Security check failed.', 'belchamber-auth-bridge'));
        }

        $admin_user_id = get_current_user_id();
        $users = get_users(array('fields' => 'ID'));
        $count = 0;
        foreach ($users as $user_id) {
            $passwords = WP_Application_Passwords::get_user_application_passwords($user_id);
            if (!empty($passwords)) {
                foreach ($passwords as $p) {
                    WP_Application_Passwords::delete_application_password($user_id, $p['uuid']);
                    Belchamber_Auth_Bridge_Logger::get_instance()->log_event($user_id, $p['name'], 'admin_kill_switch', $p['uuid'], '', $admin_user_id);
                    $count++;
                }
            }
        }

        $msg = sprintf(__('Emergency Revocation Complete: Revoked %d application connections.', 'belchamber-auth-bridge'), $count);
        wp_safe_redirect(admin_url('tools.php?page=belchamber-auth-bridge-connections&tab=connections&message=' . urlencode($msg)));
        exit;
    }

    public function handle_save_settings_action() {
        if (!current_user_can('manage_options') || !check_admin_referer('belchamber_auth_bridge_save_settings_action', 'belchamber_auth_bridge_nonce')) {
            wp_die(__('Security check failed.', 'belchamber-auth-bridge'));
        }

        $admin_user_id = get_current_user_id();
        $ttl_days = isset($_POST['ttl_days']) ? (int)$_POST['ttl_days'] : 0;
        $notify_admin = isset($_POST['notify_admin']) ? '1' : '0';
        $app_whitelist = isset($_POST['app_whitelist']) ? sanitize_text_field($_POST['app_whitelist']) : '';
        $app_owners = isset($_POST['app_owners']) ? $this->parse_app_owners_text($_POST['app_owners']) : array();

        update_option('belchamber_auth_bridge_ttl_days', $ttl_days);
        update_option('belchamber_auth_bridge_notify_admin', $notify_admin);
        update_option('belchamber_auth_bridge_app_whitelist', $app_whitelist);
        update_option('belchamber_auth_bridge_app_owners', $app_owners);

        Belchamber_Auth_Bridge_Logger::get_instance()->log_event(0, 'System Settings', 'admin_settings_change', '', '', $admin_user_id);

        $msg = __('Settings successfully saved.', 'belchamber-auth-bridge');
        wp_safe_redirect(admin_url('tools.php?page=belchamber-auth-bridge-connections&tab=settings&message=' . urlencode($msg)));
        exit;
    }

    /**
     * Parses the "app_id = user_id[,user_id...]" textarea into the shape
     * stored in belchamber_auth_bridge_app_owners: array(app_id => array(user_id, ...)).
     * Blank lines and malformed lines (no "=") are ignored.
     */
    private function parse_app_owners_text($raw_text) {
        $owners = array();
        $lines = preg_split('/[\r\n]+/', (string) $raw_text);

        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || strpos($line, '=') === false) {
                continue;
            }

            list($app_id, $user_ids_raw) = array_map('trim', explode('=', $line, 2));
            $app_id = sanitize_text_field($app_id);
            if ($app_id === '') {
                continue;
            }

            $user_ids = array_filter(array_map('intval', explode(',', $user_ids_raw)));
            if (empty($user_ids)) {
                continue;
            }

            $owners[$app_id] = isset($owners[$app_id]) ? array_unique(array_merge($owners[$app_id], $user_ids)) : $user_ids;
        }

        return $owners;
    }
}

// Bootstrap plugin instance
Belchamber_Auth_Bridge::get_instance();
