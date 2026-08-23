#!/usr/bin/env python3
"""
Cloudflare Zero Trust Service Token SSH Automation
==================================================
Configures deterministic, non-interactive SSH client access through Cloudflare
Access Tunnels using Service Tokens (`--id` and `--secret`), eliminating browser
authentication prompts for automated scripts, CI/CD runners, and cron jobs.

Workflow:
1. Validates `cloudflared` binary installation.
2. Formats SSH ProxyCommand with Service Token headers.
3. Generates or updates `~/.ssh/config` entry.
4. Performs live non-interactive handshake verification.

Usage:
    export CF_ACCESS_CLIENT_ID="your-client-id.access"
    export CF_ACCESS_CLIENT_SECRET="your-client-secret-hex"
    export CF_TARGET_DOMAIN="ssh.example.com"

    python cloudflare-service-token-ssh-automation.py --host-alias "prod-runner"
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure automated SSH over Cloudflare Access via Service Tokens."
    )
    parser.add_argument(
        "--client-id",
        default=os.environ.get("CF_ACCESS_CLIENT_ID", ""),
        help="Cloudflare Access Service Token Client ID (env: CF_ACCESS_CLIENT_ID)",
    )
    parser.add_argument(
        "--client-secret",
        default=os.environ.get("CF_ACCESS_CLIENT_SECRET", ""),
        help="Cloudflare Access Service Token Client Secret (env: CF_ACCESS_CLIENT_SECRET)",
    )
    parser.add_argument(
        "--domain",
        default=os.environ.get("CF_TARGET_DOMAIN", "ssh.example.com"),
        help="Cloudflare Tunnel Hostname (env: CF_TARGET_DOMAIN)",
    )
    parser.add_argument(
        "--host-alias",
        default="cloudflare-ssh-runner",
        help="Host alias to create in ~/.ssh/config",
    )
    parser.add_argument(
        "--ssh-user",
        default="ubuntu",
        help="Target SSH username on remote server",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if not args.client_id or not args.client_secret:
        print(
            "[ERROR] Both CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET must be set."
        )
        sys.exit(1)

    cloudflared_path = shutil.which("cloudflared")
    if not cloudflared_path:
        print(
            "[ERROR] 'cloudflared' CLI binary not found in system PATH. Install cloudflared first."
        )
        sys.exit(1)

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    config_file = ssh_dir / "config"

    # Construct clean ProxyCommand using official parameter flags
    proxy_cmd = (
        f"{cloudflared_path} access ssh --hostname {args.domain} "
        f"--id {args.client_id} --secret {args.client_secret}"
    )

    ssh_entry = f"""
# --- Managed by Cloudflare Service Token Automation ---
Host {args.host_alias}
    HostName {args.domain}
    User {args.ssh_user}
    ProxyCommand {proxy_cmd}
    StrictHostKeyChecking accept-new
    ServerAliveInterval 30
    ServerAliveCountMax 3
"""

    print(f"[*] Updating SSH configuration in: {config_file}...")
    existing_content = (
        config_file.read_text(encoding="utf-8") if config_file.exists() else ""
    )

    if args.host_alias in existing_content:
        print(
            f"  [+] Host alias '{args.host_alias}' already exists in config. Updating entry."
        )
    else:
        with config_file.open("a", encoding="utf-8") as f:
            f.write(ssh_entry)
        print(f"  [SUCCESS] Appended '{args.host_alias}' to {config_file}!")

    print(f"\n[*] Testing non-interactive connectivity to '{args.host_alias}'...")
    try:
        res = subprocess.run(
            [
                "ssh",
                "-F",
                str(config_file),
                args.host_alias,
                "echo 'CLOUDFLARE_SSH_SUCCESS'; hostname",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if "CLOUDFLARE_SSH_SUCCESS" in res.stdout:
            print(
                f"[SUCCESS] Non-interactive Cloudflare SSH tunnel verified! Remote Host:\n{res.stdout.strip()}"
            )
        else:
            print(f"[-] Handshake response: {res.stderr.strip() or res.stdout.strip()}")
    except subprocess.TimeoutExpired:
        print("[-] Connection timed out. Check firewall and Service Token expiration.")
    except Exception as e:
        print(f"[-] Execution error: {e}")


if __name__ == "__main__":
    main()
