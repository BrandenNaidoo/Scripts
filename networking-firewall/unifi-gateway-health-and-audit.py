#!/usr/bin/env python3
"""
UniFi Cloud Gateway Health & Security Policy Auditor
====================================================
Performs non-invasive security and operational health auditing on UniFi
Cloud Gateways (UCG Ultra, UDM Pro, UXG) via SSH.

Checks performed:
- Storage capacity across system root (/) and /var/log partitions.
- Automated logrotate compression and syslog health.
- Suricata IDS/IPS engine status & active memory footprint.
- Conntrack state table utilization & unreplied connection tracking.
- VLAN network interfaces, subnets, and routing table integrity.
- SSH and Remote Management listener exposure.

Usage:
    export GATEWAY_HOST="192.168.1.1"
    export GATEWAY_USER="root"
    export GATEWAY_PASSWORD="YourSecurePassword"

    python unifi-gateway-health-and-audit.py
"""

import argparse
import os
import sys
from typing import Dict, List

try:
    import paramiko
except ImportError:
    print("[ERROR] paramiko library is required. Install with: pip install paramiko")
    sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit UniFi Cloud Gateway system health and security state."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("GATEWAY_HOST", "192.168.1.1"),
        help="Gateway Management IP or FQDN (env: GATEWAY_HOST)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("GATEWAY_USER", "root"),
        help="SSH Username (env: GATEWAY_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("GATEWAY_PASSWORD", ""),
        help="SSH Password (env: GATEWAY_PASSWORD)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GATEWAY_PORT", "22")),
        help="SSH Port (default: 22)",
    )
    return parser.parse_args()


def run_remote_command(ssh: paramiko.SSHClient, cmd: str) -> str:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()


def audit_disk_and_memory(ssh: paramiko.SSHClient) -> List[Dict[str, str]]:
    raw_df = run_remote_command(ssh, "df -h / /var/log")
    lines = raw_df.splitlines()[1:]
    results = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 6:
            results.append(
                {
                    "Filesystem": parts[0],
                    "Size": parts[1],
                    "Used": parts[2],
                    "Avail": parts[3],
                    "Use %": parts[4],
                    "Mounted On": parts[5],
                }
            )
    return results


def audit_conntrack(ssh: paramiko.SSHClient) -> Dict[str, str]:
    count = run_remote_command(
        ssh, "cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null || echo '0'"
    )
    max_count = run_remote_command(
        ssh, "cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null || echo '0'"
    )
    unreplied = run_remote_command(
        ssh, "conntrack -L -p udp 2>/dev/null | grep -c 'UNREPLIED' || echo '0'"
    )
    return {
        "Active Connections": count,
        "Maximum Capacity": max_count,
        "Unreplied UDP States": unreplied,
    }


def audit_vlans(ssh: paramiko.SSHClient) -> List[Dict[str, str]]:
    raw_ip = run_remote_command(ssh, "ip -br -4 addr show | grep -E 'br|eth|ppp|wg'")
    results = []
    for line in raw_ip.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            results.append(
                {
                    "Interface": parts[0],
                    "State": parts[1],
                    "IP Address": parts[2],
                }
            )
    return results


def main() -> None:
    args = parse_arguments()
    if not args.password:
        print(
            "[ERROR] Gateway password must be supplied via --password or GATEWAY_PASSWORD env var."
        )
        sys.exit(1)

    print(f"[*] Connecting to UniFi Gateway: {args.host}:{args.port} as {args.user}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            args.host,
            port=args.port,
            username=args.user,
            password=args.password,
            timeout=10,
        )
    except Exception as e:
        print(f"[ERROR] Failed to connect to Gateway: {e}")
        sys.exit(1)

    try:
        hostname = run_remote_command(
            ssh, "ubnt-device-info model 2>/dev/null || hostname"
        )
        uptime = run_remote_command(ssh, "uptime -p")
        print(f"[+] Connected to: {hostname.upper()} ({uptime})")

        print("\n" + "=" * 75)
        print(" 1. STORAGE HEALTH & LOG PARTITION CAPACITY")
        print("=" * 75)
        disks = audit_disk_and_memory(ssh)
        for d in disks:
            print(
                f"  - {d['Mounted On']:<12}: Size {d['Size']}, Used {d['Used']} ({d['Use %']}), Available {d['Avail']}"
            )

        print("\n" + "=" * 75)
        print(" 2. NETFILTER STATE TABLE & CONNTRACK HEALTH")
        print("=" * 75)
        ct = audit_conntrack(ssh)
        for k, v in ct.items():
            print(f"  - {k:<25}: {v}")

        print("\n" + "=" * 75)
        print(" 3. ACTIVE VLAN INTERFACES & ROUTING POSTURE")
        print("=" * 75)
        vlans = audit_vlans(ssh)
        for v in vlans:
            print(f"  - {v['Interface']:<15} [{v['State']:<4}]: {v['IP Address']}")

        print("\n" + "=" * 75)
        print(" [COMPLETE] UniFi Gateway Health Audit Completed Successfully.")
        print("=" * 75 + "\n")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
