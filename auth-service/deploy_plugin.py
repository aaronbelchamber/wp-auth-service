"""
Plugin Deployer.

Standalone deployment script that reads site configuration from the site-manager
`sites.yaml` and `credentials.enc` files WITHOUT importing site-manager Python modules.

This decoupled design means changes to site-manager internals will never silently
break this deployer. Only the config file formats (sites.yaml / credentials.enc)
act as the shared contract — and those are stable, versioned YAML/JSON structures.

Deploys ANY plugin listed in plugins/plugin-manifest.json (the same manifest
build-plugins.ps1, bump-version.ps1, and publish-plugin.ps1 read from), not
just one hardcoded plugin — pass --plugin <slug>.

Usage:
    python deploy_plugin.py --plugin belchamber-auth-bridge --site tools-belchamber-us [--dry-run] [--no-git]
"""

import argparse
import io
import json
import os
import sys
import socket
import subprocess
import yaml
import paramiko

from pathlib import Path
from typing import Optional

from _credentials import parse_credentials_blob


# ─── Paths ────────────────────────────────────────────────────────────────────

PLUGINS_DIR = Path(__file__).resolve().parent.parent
PLUGIN_MANIFEST_PATH = PLUGINS_DIR / "plugin-manifest.json"
SITE_MANAGER_DIR = Path(__file__).resolve().parent.parent.parent / "site-ops"
SITES_YAML = SITE_MANAGER_DIR / "config" / "sites.yaml"
CREDENTIALS_ENC = Path.home() / ".wp_site_manager" / "credentials.enc"


def resolve_plugin_src(plugin_slug: str) -> Path:
    """Resolve a plugin slug to its source folder via plugin-manifest.json --
    the same manifest build-plugins.ps1/bump-version.ps1/publish-plugin.ps1 use,
    so all four tools agree on where a given plugin actually lives."""
    if not PLUGIN_MANIFEST_PATH.exists():
        raise FileNotFoundError(f"plugin-manifest.json not found at: {PLUGIN_MANIFEST_PATH}")
    with open(PLUGIN_MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    if plugin_slug not in manifest:
        available = ", ".join(manifest.keys())
        raise ValueError(f"Unknown plugin slug '{plugin_slug}'. Known slugs: {available}")
    return PLUGINS_DIR / manifest[plugin_slug]


# ─── Site Config Reader ────────────────────────────────────────────────────────

class SiteConfigReader:
    """
    Reads site-manager's sites.yaml and credentials.enc without importing
    site-manager Python modules. Treats the YAML/JSON files as the stable
    integration contract.
    """

    def __init__(self, sites_yaml: Path = SITES_YAML, credentials_enc: Path = CREDENTIALS_ENC) -> None:
        self._sites_yaml = sites_yaml
        self._credentials_enc = credentials_enc

    def load_site(self, site_name: str) -> dict:
        """Load a named site definition from sites.yaml."""
        if not self._sites_yaml.exists():
            raise FileNotFoundError(f"sites.yaml not found at: {self._sites_yaml}")
        with open(self._sites_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        sites = data.get("sites", {})
        if site_name not in sites:
            available = ", ".join(sites.keys())
            raise ValueError(f"Site '{site_name}' not found in sites.yaml. Available: {available}")
        site = sites[site_name]
        site["site_name"] = site_name
        return site

    def load_credentials(self, profile_name: str) -> dict:
        """
        Load SSH credentials for a named credential_profile.
        Decrypts credentials.enc if available, or falls back to environment variables.
        """
        # Try env vars first (CI / manual override)
        env_user = os.environ.get("WP_DEPLOY_USER")
        env_host = os.environ.get("WP_DEPLOY_HOST")
        env_key = os.environ.get("WP_DEPLOY_SSH_KEY")
        env_pass = os.environ.get("WP_DEPLOY_PASSWORD")

        if env_host:
            return {
                "ssh_host": env_host,
                "ssh_port": int(os.environ.get("WP_DEPLOY_PORT", 22)),
                "ssh_user": env_user or "root",
                "ssh_private_key": env_key,
                "ssh_password": env_pass,
            }

        # Attempt to decrypt credentials.enc from ~/.wp_site_manager/credentials.enc
        if self._credentials_enc.exists():
            enc_key = os.environ.get("ENCRYPTION_KEY")
            if not enc_key:
                # Read ENCRYPTION_KEY from site-manager/config/.env if not in environment
                sm_env = SITE_MANAGER_DIR / "config" / ".env"
                if sm_env.exists():
                    with open(sm_env, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("ENCRYPTION_KEY="):
                                enc_key = line.split("=", 1)[1].strip()
                                break

            if enc_key:
                try:
                    import base64
                    from cryptography.fernet import Fernet
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

                    with open(self._credentials_enc, "rb") as f:
                        data = f.read()
                    salt, ciphertext, _iterations = parse_credentials_blob(data)

                    kdf = PBKDF2HMAC(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=salt,
                        iterations=_iterations,
                    )
                    key = base64.urlsafe_b64encode(kdf.derive(enc_key.encode("utf-8")))
                    fernet = Fernet(key)
                    raw_decrypted = fernet.decrypt(ciphertext).decode("utf-8")
                    raw = json.loads(raw_decrypted)
                    profiles = raw.get("_profiles", raw)
                    if profile_name in profiles:
                        return profiles[profile_name]
                except Exception as e:
                    pass

        raise RuntimeError(
            f"Cannot resolve credentials for profile '{profile_name}'.\n"
            "Please set environment variables:\n"
            "  WP_DEPLOY_HOST, WP_DEPLOY_USER, WP_DEPLOY_SSH_KEY or WP_DEPLOY_PASSWORD"
        )


# ─── SSH File Deployer ─────────────────────────────────────────────────────────

class PluginDeployer:
    """
    Transfers plugin files to a remote WordPress server via SFTP (Paramiko).
    Self-contained — no dependency on site-manager Python classes.
    """

    def __init__(self, host: str, port: int, user: str, private_key: Optional[str], password: Optional[str]) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._private_key = private_key
        self._password = password
        self._client: Optional[paramiko.SSHClient] = None

    def connect(self) -> None:
        """Establish authenticated SSH connection."""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: dict = {
            "hostname": self._host,
            "port": self._port,
            "username": self._user,
            "timeout": 20,
        }

        if self._private_key:
            key_str = self._private_key.strip()
            if not key_str.startswith("-----BEGIN") and "\n" not in key_str:
                expanded = os.path.expanduser(key_str)
                if os.path.isfile(expanded):
                    connect_kwargs["key_filename"] = expanded
                else:
                    pkey = self._parse_key(key_str)
                    connect_kwargs["pkey"] = pkey
            else:
                pkey = self._parse_key(key_str)
                connect_kwargs["pkey"] = pkey

        if self._password:
            connect_kwargs["password"] = self._password

        self._client.connect(**connect_kwargs)
        print(f"  [OK] Connected to {self._user}@{self._host}:{self._port}")

    def _parse_key(self, key_str: str) -> paramiko.PKey:
        """Try multiple key types to parse the private key."""
        key_classes = []
        for name in ["Ed25519Key", "RSAKey", "ECDSAKey", "DSSKey"]:
            cls = getattr(paramiko, name, None)
            if cls is not None:
                key_classes.append(cls)

        for key_class in key_classes:
            try:
                return key_class.from_private_key(io.StringIO(key_str))
            except paramiko.SSHException:
                continue
        raise ValueError("Could not parse SSH private key. Ensure it is a valid PEM key.")

    def deploy(self, local_src: Path, remote_plugin_dir: str, dry_run: bool = False) -> None:
        """Recursively SFTP-upload local_src directory to remote_plugin_dir."""
        if not self._client:
            raise RuntimeError("SSH client not connected. Call connect() first.")

        sftp = self._client.open_sftp()
        self._ensure_remote_dir(sftp, remote_plugin_dir)

        for local_file in local_src.rglob("*"):
            if local_file.is_file():
                relative = local_file.relative_to(local_src)
                remote_path = f"{remote_plugin_dir.rstrip('/')}/{relative}".replace("\\", "/")
                remote_dir = "/".join(remote_path.split("/")[:-1])
                self._ensure_remote_dir(sftp, remote_dir)

                if dry_run:
                    print(f"  [DRY RUN] Would upload: {local_file} -> {remote_path}")
                else:
                    sftp.put(str(local_file), remote_path)
                    print(f"  [OK] {relative} -> {remote_path}")

        sftp.close()

    def _ensure_remote_dir(self, sftp: paramiko.SFTPClient, remote_dir: str) -> None:
        """Create remote directory tree if it does not exist."""
        parts = remote_dir.strip("/").split("/")
        current = ""
        for part in parts:
            current += f"/{part}"
            try:
                sftp.stat(current)
            except FileNotFoundError:
                sftp.mkdir(current)

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self._client:
            self._client.close()
            self._client = None


# ─── GitHub Sync ───────────────────────────────────────────────────────────────

class GitHubSyncer:
    """
    Commits and pushes current changes to the containing repo's GitHub origin.

    cwd is set to the plugin's own source directory (not a hardcoded repo
    root), so `git add .` only stages that plugin's own changes even though
    every plugin under plugins/ lives in the same monorepo -- deploying
    image-webp-converter never accidentally sweeps up unrelated
    belchamber-auth-bridge changes, or vice versa. git commit/push still
    operate on the whole repo's shared branch, same as running git from any
    subdirectory of a repo normally would.
    """

    def __init__(self, plugin_dir: Path, commit_message: str) -> None:
        self._plugin_dir = plugin_dir
        self._commit_message = commit_message

    def sync(self) -> bool:
        """Stage all, commit if changes exist, and push to origin/main."""
        try:
            remote_url = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self._plugin_dir, capture_output=True, text=True, check=True
            ).stdout.strip()
        except subprocess.CalledProcessError:
            print("  [ERROR] Git sync failed: no 'origin' remote configured for this repo.")
            return False

        try:
            subprocess.run(["git", "add", "."], cwd=self._plugin_dir, check=True)
            result = subprocess.run(
                ["git", "commit", "-m", self._commit_message],
                cwd=self._plugin_dir, capture_output=True, text=True
            )
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print("  [INFO] No new changes to commit. Pushing existing state...")
            else:
                print(f"  [OK] Committed: {self._commit_message}")

            subprocess.run(["git", "push", "origin", "main"], cwd=self._plugin_dir, check=True)
            print(f"  [OK] Pushed to {remote_url}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"  [ERROR] Git sync failed: {e}")
            return False


# ─── CLI Entrypoint ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy a plugin (from plugin-manifest.json) to a WordPress site managed by site-manager."
    )
    parser.add_argument(
        "--plugin", required=True,
        help="Plugin slug as defined in plugins/plugin-manifest.json (e.g. belchamber-auth-bridge)"
    )
    parser.add_argument(
        "--site", required=True,
        help="Site slug as defined in site-manager's sites.yaml (e.g. tools-belchamber-us)"
    )
    parser.add_argument("--plugin-dir", default=None, help="Override remote plugin directory path")
    parser.add_argument("--dry-run", action="store_true", help="Simulate deployment without transferring files")
    parser.add_argument("--no-git", action="store_true", help="Skip GitHub cloud backup push")
    parser.add_argument("--commit-message", default=None, help="Git commit message (default: 'Deploy <plugin> update')")
    args = parser.parse_args()

    try:
        plugin_src = resolve_plugin_src(args.plugin)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    commit_message = args.commit_message or f"Deploy {args.plugin} update"

    print("\n===========================================================")
    print(f" Plugin Deployer")
    print(f"    Plugin      : {args.plugin}")
    print(f"    Target Site : {args.site}")
    print(f"    Dry Run     : {'Yes' if args.dry_run else 'No'}")
    print("===========================================================\n")

    # Step 1: GitHub cloud backup
    if not args.no_git:
        print("[Step 1/2] Syncing to GitHub cloud backup...")
        syncer = GitHubSyncer(plugin_dir=plugin_src, commit_message=commit_message)
        syncer.sync()
    else:
        print("[Step 1/2] Skipping GitHub sync (--no-git).")

    # Step 2: Load site config from site-manager sites.yaml
    print(f"\n[Step 2/2] Deploying plugin to WordPress site '{args.site}'...")
    reader = SiteConfigReader()
    try:
        site = reader.load_site(args.site)
    except (FileNotFoundError, ValueError) as e:
        print(f"  [ERROR] {e}")
        sys.exit(1)

    credential_profile = site.get("credential_profile")
    try:
        creds = reader.load_credentials(credential_profile)
    except RuntimeError as e:
        print(f"  [ERROR] {e}")
        sys.exit(1)

    ssh_host = creds.get("ssh_host") or site.get("ssh_host")
    ssh_port = int(creds.get("ssh_port", site.get("ssh_port", 22)))
    ssh_user = creds.get("ssh_user") or site.get("ssh_user", "root")
    ssh_key = creds.get("ssh_private_key")
    ssh_pass = creds.get("ssh_password")

    # Remote plugin path: prefer an explicit --plugin-dir override, then a
    # per-site plugin_path from sites.yaml, then fall back to naively
    # deriving it from wp_path. The naive derivation assumes wp-content
    # lives directly under wp_path, which is wrong for sites where
    # WordPress core is installed in its own subdirectory (e.g. .../cms/)
    # with wp-content elsewhere — set plugin_path explicitly in sites.yaml
    # for any site shaped like that.
    wp_path = site.get("wp_path", "").rstrip("/")
    remote_plugin_dir = (
        args.plugin_dir
        or site.get("plugin_path")
        or f"{wp_path}/wp-content/plugins/{args.plugin}"
    )

    print(f"  Host       : {ssh_user}@{ssh_host}:{ssh_port}")
    print(f"  Plugin Dir : {remote_plugin_dir}")
    print(f"  Local Src  : {plugin_src}\n")

    deployer = PluginDeployer(ssh_host, ssh_port, ssh_user, ssh_key, ssh_pass)
    try:
        deployer.connect()
        deployer.deploy(plugin_src, remote_plugin_dir, dry_run=args.dry_run)
        print(f"\n[OK] {'Dry run complete.' if args.dry_run else 'Plugin deployed successfully!'}")
    except Exception as e:
        print(f"\n[ERROR] Deployment failed: {e}")
        sys.exit(1)
    finally:
        deployer.disconnect()


if __name__ == "__main__":
    main()
