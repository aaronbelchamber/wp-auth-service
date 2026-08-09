<?php
/**
 * Plugin Name: WP App Bridge & Session Storage
 * Plugin URI:  https://github.com/your-repo/wp-app-bridge
 * Description: Lightweight WordPress plugin providing custom DB session storage, REST API endpoints, and centralized Application Password connection management, logging, and security tools.
 * Version:     1.2.0
 * Author:      Anti-Gravity
 * License:     MIT
 * Text Domain: wp-app-bridge
 */

if (!defined('ABSPATH')) {
    exit; // Exit if accessed directly.
}

define('WP_APP_BRIDGE_VERSION', '1.2.0');
define('WP_APP_BRIDGE_DB_VERSION', '1.2.0');

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
class WP_App_Bridge {
    private static $instance = null;

    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        $this->init_hooks();
        WP_App_Bridge_Logger::get_instance();
        WP_App_Bridge_Security::get_instance();
        if (is_admin()) {
            WP_App_Bridge_Admin::get_instance();
        }
    }

    private function init_hooks() {
        register_activation_hook(__FILE__, array('WP_App_Bridge_DB', 'activate'));
        add_action('wp_authorize_application_password_request_errors', array($this, 'handle_loopback_and_whitelist_errors'), 99999, 3);
        add_action('rest_api_init', array($this, 'register_rest_routes'));
    }

    /**
     * Handle loopback callback errors and enforce app whitelist if enabled.
     */
    public function handle_loopback_and_whitelist_errors($error, $request, $user) {
        if (!is_wp_error($error)) {
            $error = new WP_Error();
        }

        // Whitelist Check
        $whitelist_setting = get_option('wp_app_bridge_app_whitelist', '');
        if (!empty($whitelist_setting) && !empty($request['app_name'])) {
            $allowed_apps = array_map('trim', explode(',', strtolower($whitelist_setting)));
            if (!in_array(strtolower($request['app_name']), $allowed_apps, true)) {
                $error->add('app_not_whitelisted', __('This application name is not authorized to connect to this WordPress site.', 'wp-app-bridge'));
                return;
            }
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
     * Register REST API Endpoints under namespace 'app/v1'.
     */
    public function register_rest_routes() {
        register_rest_route('app/v1', '/health', array(
            'methods'             => WP_REST_Server::READABLE,
            'callback'            => array($this, 'health_check'),
            'permission_callback' => '__return_true',
        ));

        register_rest_route('app/v1', '/session', array(
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
        return rest_ensure_response(array(
            'status'  => 'active',
            'plugin'  => 'wp-app-bridge',
            'version' => WP_APP_BRIDGE_VERSION,
        ));
    }

    public function permissions_check($request) {
        if (!is_user_logged_in()) {
            return new WP_Error('rest_forbidden', __('You must be logged in to perform this operation.', 'wp-app-bridge'), array('status' => 401));
        }
        return true;
    }

    public function get_session($request) {
        global $wpdb;
        $user_id = get_current_user_id();
        $app_id = $request->get_param('app_id');
        $session_key = $request->get_param('session_key');

        $table_name = $wpdb->prefix . 'app_sessions';
        $row = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM $table_name WHERE user_id = %d AND app_id = %s AND session_key = %s LIMIT 1",
            $user_id, $app_id, $session_key
        ));

        if (!$row) {
            return new WP_Error('session_not_found', __('Session entry not found.', 'wp-app-bridge'), array('status' => 404));
        }

        WP_App_Bridge_Logger::get_instance()->log_event($user_id, $app_id, 'session_read', '', $session_key);

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

        if (is_array($payload_raw) || is_object($payload_raw)) {
            $payload_str = wp_json_encode($payload_raw);
        } else {
            $payload_str = (string)$payload_raw;
        }

        $now = time();
        $table_name = $wpdb->prefix . 'app_sessions';

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
                return new WP_Error('db_update_error', __('Failed to update session payload.', 'wp-app-bridge'), array('status' => 500));
            }

            WP_App_Bridge_Logger::get_instance()->log_event($user_id, $app_id, 'session_write', '', $session_key);

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
                return new WP_Error('db_insert_error', __('Failed to insert session payload.', 'wp-app-bridge'), array('status' => 500));
            }

            WP_App_Bridge_Logger::get_instance()->log_event($user_id, $app_id, 'session_write', '', $session_key);

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

        $table_name = $wpdb->prefix . 'app_sessions';
        $deleted = $wpdb->delete(
            $table_name,
            array('user_id' => $user_id, 'app_id' => $app_id, 'session_key' => $session_key),
            array('%d', '%s', '%s')
        );

        if (!$deleted) {
            return new WP_Error('session_not_found', __('Session entry not found or already deleted.', 'wp-app-bridge'), array('status' => 404));
        }

        WP_App_Bridge_Logger::get_instance()->log_event($user_id, $app_id, 'session_delete', '', $session_key);

        return rest_ensure_response(array(
            'success' => true, 'action' => 'deleted',
            'app_id' => $app_id, 'session_key' => $session_key,
        ));
    }
}

/**
 * Database Provisioner Class
 */
class WP_App_Bridge_DB {
    public static function activate() {
        global $wpdb;

        $charset_collate = $wpdb->get_charset_collate();
        require_once(ABSPATH . 'wp-admin/includes/upgrade.php');

        // Sessions Table
        $table_sessions = $wpdb->prefix . 'app_sessions';
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

        // Audit Logs Table with admin_user_id tracking
        $table_logs = $wpdb->prefix . 'app_auth_logs';
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

        add_option('wp_app_bridge_db_version', WP_APP_BRIDGE_DB_VERSION);
    }
}

/**
 * Audit Logger Class
 */
class WP_App_Bridge_Logger {
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
        $table_name = $wpdb->prefix . 'app_auth_logs';
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
                        $transient_key = 'wp_app_bridge_log_use_' . $p['uuid'];
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
class WP_App_Bridge_Security {
    private static $instance = null;

    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_action('wp_create_application_password', array($this, 'notify_admin_on_high_privilege_auth'), 10, 4);
        add_action('wp_app_bridge_ttl_cleanup', array($this, 'run_ttl_cleanup'));

        if (!wp_next_scheduled('wp_app_bridge_ttl_cleanup')) {
            wp_schedule_event(time(), 'daily', 'wp_app_bridge_ttl_cleanup');
        }
    }

    public function notify_admin_on_high_privilege_auth($user_id, $new_item, $new_password, $args) {
        $enabled = get_option('wp_app_bridge_notify_admin', '1');
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

    public function run_ttl_cleanup() {
        $ttl_days = (int)get_option('wp_app_bridge_ttl_days', 0);
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
                    WP_App_Bridge_Logger::get_instance()->log_event(
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
class WP_App_Bridge_Admin {
    private static $instance = null;

    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_action('admin_menu', array($this, 'register_admin_menu'));
        add_action('admin_post_wp_app_bridge_revoke', array($this, 'handle_revoke_action'));
        add_action('admin_post_wp_app_bridge_purge_sessions', array($this, 'handle_purge_sessions_action'));
        add_action('admin_post_wp_app_bridge_kill_switch', array($this, 'handle_kill_switch_action'));
        add_action('admin_post_wp_app_bridge_save_settings', array($this, 'handle_save_settings_action'));
    }

    public function register_admin_menu() {
        add_management_page(
            __('App Connections', 'wp-app-bridge'),
            __('App Connections', 'wp-app-bridge'),
            'manage_options',
            'wp-app-bridge-connections',
            array($this, 'render_admin_page')
        );
    }

    public function render_admin_page() {
        if (!current_user_can('manage_options')) {
            wp_die(__('You do not have sufficient permissions to access this page.', 'wp-app-bridge'));
        }

        $active_tab = isset($_GET['tab']) ? sanitize_text_field($_GET['tab']) : 'connections';
        ?>
        <div class="wrap">
            <h1 class="wp-heading-inline">
                <span class="dashicons dashicons-rest-api" style="font-size:30px; width:30px; height:30px; margin-right:8px;"></span>
                <?php _e('Application Connections & Auth Service', 'wp-app-bridge'); ?>
            </h1>
            <hr class="wp-header-end">

            <?php if (isset($_GET['message'])) : ?>
                <div class="notice notice-success is-dismissible">
                    <p><?php echo esc_html(sanitize_text_field($_GET['message'])); ?></p>
                </div>
            <?php endif; ?>

            <nav class="nav-tab-wrapper">
                <a href="?page=wp-app-bridge-connections&tab=connections" class="nav-tab <?php echo $active_tab === 'connections' ? 'nav-tab-active' : ''; ?>">
                    <?php _e('Active Connections', 'wp-app-bridge'); ?>
                </a>
                <a href="?page=wp-app-bridge-connections&tab=logs" class="nav-tab <?php echo $active_tab === 'logs' ? 'nav-tab-active' : ''; ?>">
                    <?php _e('Audit Logs', 'wp-app-bridge'); ?>
                </a>
                <a href="?page=wp-app-bridge-connections&tab=settings" class="nav-tab <?php echo $active_tab === 'settings' ? 'nav-tab-active' : ''; ?>">
                    <?php _e('Security & Settings', 'wp-app-bridge'); ?>
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
                    <h2 style="margin-top:0;"><?php _e('Active Authorized Applications Across All Users', 'wp-app-bridge'); ?></h2>
                    <p class="description"><?php _e('Monitor external applications currently authorized via WordPress Application Passwords. You can revoke access or purge stored session data for any application connection.', 'wp-app-bridge'); ?></p>
                </div>
                <div>
                    <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>" onsubmit="return confirm('WARNING: Are you sure you want to revoke ALL application connections site-wide? Existing app sessions will be terminated immediately.');">
                        <?php wp_nonce_field('wp_app_bridge_kill_switch_action', 'wp_app_bridge_nonce'); ?>
                        <input type="hidden" name="action" value="wp_app_bridge_kill_switch">
                        <button type="submit" class="button button-link-delete" style="color:#d63638; text-decoration:none;">
                            <span class="dashicons dashicons-shield-alt" style="vertical-align:middle;"></span>
                            <?php _e('Emergency Revoke All Connections', 'wp-app-bridge'); ?>
                        </button>
                    </form>
                </div>
            </div>
        </div>

        <table class="wp-list-table widefat fixed striped">
            <thead>
                <tr>
                    <th scope="col"><?php _e('User', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('Application Name', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('App ID / UUID', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('Created Date', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('Last Activity', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('Remote Sessions', 'wp-app-bridge'); ?></th>
                    <th scope="col" style="text-align:right;"><?php _e('Actions', 'wp-app-bridge'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($all_connections)) : ?>
                    <tr>
                        <td colspan="7"><?php _e('No active application connections found.', 'wp-app-bridge'); ?></td>
                    </tr>
                <?php else : ?>
                    <?php foreach ($all_connections as $conn) :
                        $table_sessions = $wpdb->prefix . 'app_sessions';
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
                                    <?php echo esc_html(human_time_diff($conn['last_used'], time())) . ' ' . __('ago', 'wp-app-bridge'); ?>
                                    <?php if (!empty($conn['last_ip'])) : ?>
                                        <br><span class="description">IP: <?php echo esc_html($conn['last_ip']); ?></span>
                                    <?php endif; ?>
                                <?php else : ?>
                                    <span class="description"><?php _e('Never used', 'wp-app-bridge'); ?></span>
                                <?php endif; ?>
                            </td>
                            <td>
                                <span class="badge" style="background:#f0f0f1; padding:3px 8px; border-radius:10px; font-weight:600;">
                                    <?php echo sprintf(_n('%d Session', '%d Sessions', $session_count, 'wp-app-bridge'), $session_count); ?>
                                </span>
                                <?php if ($session_count > 0) :
                                    $table_sessions = $wpdb->prefix . 'app_sessions';
                                    $session_rows = $wpdb->get_results($wpdb->prepare(
                                        "SELECT id, app_id, session_key, payload, updated_at FROM $table_sessions WHERE user_id = %d AND (app_id = %s OR app_id = %s) ORDER BY updated_at DESC LIMIT 10",
                                        $conn['user_id'], $conn['app_name'], $conn['app_id']
                                    ));
                                    $json_data = esc_attr(wp_json_encode($session_rows));
                                ?>
                                    <br><button type="button" class="button button-small" style="margin-top:4px; font-size:11px;" onclick='wpAppBridgeViewData(<?php echo $json_data; ?>)'>
                                        <span class="dashicons dashicons-visibility" style="font-size:14px; vertical-align:middle;"></span> <?php _e('View Data', 'wp-app-bridge'); ?>
                                    </button>
                                <?php endif; ?>
                            </td>
                            <td style="text-align:right;">
                                <div style="display:flex; justify-content:flex-end; gap:8px;">
                                    <?php if ($session_count > 0) : ?>
                                        <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
                                            <?php wp_nonce_field('wp_app_bridge_purge_sessions_action', 'wp_app_bridge_nonce'); ?>
                                            <input type="hidden" name="action" value="wp_app_bridge_purge_sessions">
                                            <input type="hidden" name="user_id" value="<?php echo esc_attr($conn['user_id']); ?>">
                                            <input type="hidden" name="app_name" value="<?php echo esc_attr($conn['app_name']); ?>">
                                            <input type="hidden" name="app_id" value="<?php echo esc_attr($conn['app_id']); ?>">
                                            <button type="submit" class="button button-secondary button-small">
                                                <?php _e('Clear Sessions', 'wp-app-bridge'); ?>
                                            </button>
                                        </form>
                                    <?php endif; ?>

                                    <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>" onsubmit="return confirm('Are you sure you want to revoke access for this application?');">
                                        <?php wp_nonce_field('wp_app_bridge_revoke_action', 'wp_app_bridge_nonce'); ?>
                                        <input type="hidden" name="action" value="wp_app_bridge_revoke">
                                        <input type="hidden" name="user_id" value="<?php echo esc_attr($conn['user_id']); ?>">
                                        <input type="hidden" name="uuid" value="<?php echo esc_attr($conn['uuid']); ?>">
                                        <button type="submit" class="button button-link-delete button-small" style="color:#d63638;">
                                            <?php _e('Revoke', 'wp-app-bridge'); ?>
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
        <div id="wp-app-bridge-modal" style="display:none; position:fixed; z-index:99999; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.6); align-items:center; justify-content:center;">
            <div style="background:#fff; width:90%; max-width:650px; border-radius:8px; padding:20px; box-shadow:0 10px 25px rgba(0,0,0,0.3); max-height:80vh; overflow-y:auto;">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #ddd; padding-bottom:10px; margin-bottom:15px;">
                    <h3 style="margin:0; font-size:18px;"><?php _e('Stored Session Payloads', 'wp-app-bridge'); ?></h3>
                    <button type="button" onclick="document.getElementById('wp-app-bridge-modal').style.display='none';" style="background:none; border:none; font-size:20px; cursor:pointer;">&times;</button>
                </div>
                <div id="wp-app-bridge-modal-content"></div>
            </div>
        </div>

        <script>
            function wpAppBridgeViewData(sessions) {
                var container = document.getElementById('wp-app-bridge-modal-content');
                if (!sessions || !sessions.length) {
                    container.innerHTML = '<p><?php _e('No session data found.', 'wp-app-bridge'); ?></p>';
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
                document.getElementById('wp-app-bridge-modal').style.display = 'flex';
            }
        </script>
        <?php
    }

    private function render_logs_tab() {
        global $wpdb;
        $table_logs = $wpdb->prefix . 'app_auth_logs';
        $logs = $wpdb->get_results("SELECT l.*, u1.user_login as target_login, u2.user_login as admin_login FROM $table_logs l LEFT JOIN {$wpdb->users} u1 ON l.user_id = u1.ID LEFT JOIN {$wpdb->users} u2 ON l.admin_user_id = u2.ID ORDER BY l.created_at DESC LIMIT 100");
        ?>
        <h2><?php _e('Application Authorization Audit Trail', 'wp-app-bridge'); ?></h2>
        <p class="description"><?php _e('Recent connection events including authorization creation, API activity, auto-expirations, and admin management actions.', 'wp-app-bridge'); ?></p>

        <table class="wp-list-table widefat fixed striped" style="margin-top:15px;">
            <thead>
                <tr>
                    <th scope="col"><?php _e('Timestamp', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('Target User ID', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('Performed By (Admin User ID)', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('Application Name', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('Event Type', 'wp-app-bridge'); ?></th>
                    <th scope="col"><?php _e('IP Address', 'wp-app-bridge'); ?></th>
                </tr>
            </thead>
            <tbody>
                <?php if (empty($logs)) : ?>
                    <tr>
                        <td colspan="6"><?php _e('No log entries recorded yet.', 'wp-app-bridge'); ?></td>
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
        $ttl_days = (int)get_option('wp_app_bridge_ttl_days', 0);
        $notify_admin = get_option('wp_app_bridge_notify_admin', '1');
        $whitelist = get_option('wp_app_bridge_app_whitelist', '');
        ?>
        <h2><?php _e('Security & App Bridge Settings', 'wp-app-bridge'); ?></h2>
        <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>" style="max-width:700px; margin-top:20px;">
            <?php wp_nonce_field('wp_app_bridge_save_settings_action', 'wp_app_bridge_nonce'); ?>
            <input type="hidden" name="action" value="wp_app_bridge_save_settings">

            <table class="form-table">
                <tr>
                    <th scope="row"><label for="ttl_days"><?php _e('Auto-Revoke Inactive Apps (TTL)', 'wp-app-bridge'); ?></label></th>
                    <td>
                        <select name="ttl_days" id="ttl_days">
                            <option value="0" <?php selected($ttl_days, 0); ?>><?php _e('Disabled (Never Auto-Revoke)', 'wp-app-bridge'); ?></option>
                            <option value="30" <?php selected($ttl_days, 30); ?>><?php _e('30 Days of Inactivity', 'wp-app-bridge'); ?></option>
                            <option value="60" <?php selected($ttl_days, 60); ?>><?php _e('60 Days of Inactivity', 'wp-app-bridge'); ?></option>
                            <option value="90" <?php selected($ttl_days, 90); ?>><?php _e('90 Days of Inactivity', 'wp-app-bridge'); ?></option>
                        </select>
                        <p class="description"><?php _e('Automatically revoke application passwords that have not been used within the specified timeframe.', 'wp-app-bridge'); ?></p>
                    </td>
                </tr>
                <tr>
                    <th scope="row"><?php _e('Admin Email Alerts', 'wp-app-bridge'); ?></th>
                    <td>
                        <label for="notify_admin">
                            <input type="checkbox" name="notify_admin" id="notify_admin" value="1" <?php checked($notify_admin, '1'); ?>>
                            <?php _e('Send email alert to site admin when an Administrator authorizes a new external app', 'wp-app-bridge'); ?>
                        </label>
                    </td>
                </tr>
                <tr>
                    <th scope="row"><label for="app_whitelist"><?php _e('Allowed Application Names Whitelist', 'wp-app-bridge'); ?></label></th>
                    <td>
                        <input type="text" name="app_whitelist" id="app_whitelist" class="large-text" value="<?php echo esc_attr($whitelist); ?>" placeholder="e.g. My Next.js App, Mobile Client, Internal CLI">
                        <p class="description"><?php _e('Comma-separated list of approved application names. Leave blank to allow any application name.', 'wp-app-bridge'); ?></p>
                    </td>
                </tr>
            </table>

            <?php submit_button(__('Save Settings', 'wp-app-bridge')); ?>
        </form>
        <?php
    }

    public function handle_revoke_action() {
        if (!current_user_can('manage_options') || !check_admin_referer('wp_app_bridge_revoke_action', 'wp_app_bridge_nonce')) {
            wp_die(__('Security check failed.', 'wp-app-bridge'));
        }

        $user_id = isset($_POST['user_id']) ? (int)$_POST['user_id'] : 0;
        $uuid = isset($_POST['uuid']) ? sanitize_text_field($_POST['uuid']) : '';
        $admin_user_id = get_current_user_id();

        if ($user_id > 0 && !empty($uuid)) {
            WP_Application_Passwords::delete_application_password($user_id, $uuid);
            WP_App_Bridge_Logger::get_instance()->log_event($user_id, 'App Connection', 'admin_revoke', $uuid, '', $admin_user_id);
            $msg = __('Application connection successfully revoked.', 'wp-app-bridge');
        } else {
            $msg = __('Invalid parameters for revocation.', 'wp-app-bridge');
        }

        wp_safe_redirect(admin_url('tools.php?page=wp-app-bridge-connections&tab=connections&message=' . urlencode($msg)));
        exit;
    }

    public function handle_purge_sessions_action() {
        if (!current_user_can('manage_options') || !check_admin_referer('wp_app_bridge_purge_sessions_action', 'wp_app_bridge_nonce')) {
            wp_die(__('Security check failed.', 'wp-app-bridge'));
        }

        global $wpdb;
        $user_id = isset($_POST['user_id']) ? (int)$_POST['user_id'] : 0;
        $app_name = isset($_POST['app_name']) ? sanitize_text_field($_POST['app_name']) : '';
        $app_id = isset($_POST['app_id']) ? sanitize_text_field($_POST['app_id']) : '';
        $admin_user_id = get_current_user_id();

        $table_sessions = $wpdb->prefix . 'app_sessions';
        $deleted = $wpdb->query($wpdb->prepare(
            "DELETE FROM $table_sessions WHERE user_id = %d AND (app_id = %s OR app_id = %s)",
            $user_id, $app_name, $app_id
        ));

        WP_App_Bridge_Logger::get_instance()->log_event($user_id, $app_name, 'admin_purge_sessions', '', $app_id, $admin_user_id);

        $msg = sprintf(__('Cleared %d remote session records.', 'wp-app-bridge'), (int)$deleted);
        wp_safe_redirect(admin_url('tools.php?page=wp-app-bridge-connections&tab=connections&message=' . urlencode($msg)));
        exit;
    }

    public function handle_kill_switch_action() {
        if (!current_user_can('manage_options') || !check_admin_referer('wp_app_bridge_kill_switch_action', 'wp_app_bridge_nonce')) {
            wp_die(__('Security check failed.', 'wp-app-bridge'));
        }

        $admin_user_id = get_current_user_id();
        $users = get_users(array('fields' => 'ID'));
        $count = 0;
        foreach ($users as $user_id) {
            $passwords = WP_Application_Passwords::get_user_application_passwords($user_id);
            if (!empty($passwords)) {
                foreach ($passwords as $p) {
                    WP_Application_Passwords::delete_application_password($user_id, $p['uuid']);
                    WP_App_Bridge_Logger::get_instance()->log_event($user_id, $p['name'], 'admin_kill_switch', $p['uuid'], '', $admin_user_id);
                    $count++;
                }
            }
        }

        $msg = sprintf(__('Emergency Revocation Complete: Revoked %d application connections.', 'wp-app-bridge'), $count);
        wp_safe_redirect(admin_url('tools.php?page=wp-app-bridge-connections&tab=connections&message=' . urlencode($msg)));
        exit;
    }

    public function handle_save_settings_action() {
        if (!current_user_can('manage_options') || !check_admin_referer('wp_app_bridge_save_settings_action', 'wp_app_bridge_nonce')) {
            wp_die(__('Security check failed.', 'wp-app-bridge'));
        }

        $admin_user_id = get_current_user_id();
        $ttl_days = isset($_POST['ttl_days']) ? (int)$_POST['ttl_days'] : 0;
        $notify_admin = isset($_POST['notify_admin']) ? '1' : '0';
        $app_whitelist = isset($_POST['app_whitelist']) ? sanitize_text_field($_POST['app_whitelist']) : '';

        update_option('wp_app_bridge_ttl_days', $ttl_days);
        update_option('wp_app_bridge_notify_admin', $notify_admin);
        update_option('wp_app_bridge_app_whitelist', $app_whitelist);

        WP_App_Bridge_Logger::get_instance()->log_event(0, 'System Settings', 'admin_settings_change', '', '', $admin_user_id);

        $msg = __('Settings successfully saved.', 'wp-app-bridge');
        wp_safe_redirect(admin_url('tools.php?page=wp-app-bridge-connections&tab=settings&message=' . urlencode($msg)));
        exit;
    }
}

// Bootstrap plugin instance
WP_App_Bridge::get_instance();
