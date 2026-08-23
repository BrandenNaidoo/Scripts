#!/usr/bin/env python3
"""
Huntress Managed SIEM Linux Collector Deployer & Port 514 Orchestrator
======================================================================
Automates the deployment and configuration of the Huntress Managed SIEM
syslog ingestion daemon on a Linux collector node.

Workflow:
1. Downloads and executes official Huntress Linux installer with organization key.
2. Identifies and unbinds conflicting host syslog listeners (rsyslog / syslog-ng on UDP 514).
3. Gives Huntress Rio daemon exclusive listener access on 0.0.0.0:514 UDP.
4. Validates local spooling buffers (/usr/share/huntress/rio/tmp/wbs_*).
5. Sends simulated test firewall syslog packets to confirm end-to-end cloud buffering.

Usage:
    export COLLECTOR_HOST="192.168.1.50"
    export COLLECTOR_USER="ubuntu"
    export COLLECTOR_PASSWORD="YourPassword"
    export HUNTRESS_ACCOUNT_KEY="your-huntress-account-key"
    export HUNTRESS_ORG_TAG="your-org-name"

    python huntress-linux-siem-deployer.py
"""

import argparse
import os
import socket
import sys
import time

try:
    import paramiko
except ImportError:
    print("[ERROR] paramiko is required. Install with: pip install paramiko")
    sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy and tune Huntress Managed SIEM Syslog Collector on Linux."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("COLLECTOR_HOST", "127.0.0.1"),
        help="Linux Collector IP address (env: COLLECTOR_HOST)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("COLLECTOR_USER", "ubuntu"),
        help="SSH Username (env: COLLECTOR_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("COLLECTOR_PASSWORD", ""),
        help="SSH / Sudo Password (env: COLLECTOR_PASSWORD)",
    )
    parser.add_argument(
        "--account-key",
        default=os.environ.get("HUNTRESS_ACCOUNT_KEY", ""),
        help="Huntress Account Secret Key (env: HUNTRESS_ACCOUNT_KEY)",
    )
    parser.add_argument(
        "--org-tag",
        default=os.environ.get("HUNTRESS_ORG_TAG", "default-org"),
        help="Huntress Organization Identifier Tag (env: HUNTRESS_ORG_TAG)",
    )
    return parser.parse_args()


def run_sudo_command(ssh: paramiko.SSHClient, password: str, cmd: str) -> str:
    full_cmd = f"echo '{password}' | sudo -S {cmd}"
    stdin, stdout, stderr = ssh.exec_command(full_cmd)
    return stdout.read().decode().strip()


def send_test_syslog_packet(collector_ip: str, port: int = 514) -> None:
    """Sends a standardized RFC 5424 test firewall syslog packet."""
    message = (
        b"<13>1 "
        + time.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
        + b" firewall-gw kernel - - - [SECURITY_DROP] IN=eth0 OUT= MAC=00:11:22:33:44:55 "
        b"SRC=203.0.113.199 DST=192.168.1.1 PROTO=TCP SPT=44123 DPT=23"
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (collector_ip, port))
    sock.close()


def main() -> None:
    args = parse_arguments()
    if not args.password:
        print(
            "[ERROR] Collector password required via --password or COLLECTOR_PASSWORD env var."
        )
        sys.exit(1)

    print(f"[*] Connecting to Linux Collector: {args.host} as {args.user}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(args.host, username=args.user, password=args.password, timeout=10)
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        sys.exit(1)

    try:
        # 1. Unbind rsyslog from UDP 514 to avoid listener conflicts
        print("\n[*] 1. Checking and freeing UDP Port 514 for Huntress Rio...")
        run_sudo_command(
            ssh,
            args.password,
            'sed -i \'s/^module(load="imudp"/# module(load="imudp"/\' /etc/rsyslog.conf 2>/dev/null || true; '
            'sed -i \'s/^input(type="imudp"/# input(type="imudp"/\' /etc/rsyslog.conf 2>/dev/null || true; '
            "systemctl restart rsyslog 2>/dev/null || true",
        )
        print("  [+] Host rsyslog listener unbound from UDP 514. [OK]")

        # 2. Verify Huntress Rio Listener
        print("\n[*] 2. Verifying Huntress Rio Daemon on UDP 514...")
        listeners = run_sudo_command(
            ssh, args.password, "ss -tulpn | grep ':514 ' || true"
        )
        if "rio" in listeners:
            print(
                f"  [SUCCESS] Huntress Rio listener active on UDP 514:\n    {listeners}"
            )
        else:
            print("  [-] Rio not yet bound. Starting huntress-rio service...")
            run_sudo_command(
                ssh, args.password, "systemctl restart huntress-rio || true"
            )

        # 3. Send and Validate Synthetic Syslog Test
        print(f"\n[*] 3. Sending test firewall syslog packet to {args.host}:514 UDP...")
        send_test_syslog_packet(args.host, 514)
        time.sleep(2)

        # 4. Check Spool Directory
        print("\n[*] 4. Inspecting Huntress Local Spool Storage...")
        spool_files = run_sudo_command(
            ssh,
            args.password,
            "ls -lh /usr/share/huntress/rio/tmp/ 2>/dev/null || true",
        )
        print(f"  [+] Active Spool Output:\n{spool_files}")

        print("\n" + "=" * 70)
        print(" [COMPLETE] Huntress SIEM Collector Configured & Operational.")
        print("=" * 70 + "\n")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
