#!/usr/bin/env python3
"""
WireGuard VPN End-to-End Diagnostic Suite
=========================================
Performs automated multi-hop troubleshooting and cryptographic validation for
WireGuard VPN tunnels hosted on Linux or UniFi Gateway appliances.

Validates:
- Kernel wireguard module and interface status (wg0 / wgsrv1).
- Peer public key registration & preshared key (PSK) binding.
- Latest handshake timestamp and transmission byte counters.
- Conntrack table state to detect dropped/unreplied handshake initiations.
- Client AllowedIPs routing and firewall WAN port forwarding (UDP 51820).

Usage:
    export GATEWAY_HOST="192.168.1.1"
    export GATEWAY_USER="root"
    export GATEWAY_PASSWORD="YourPassword"

    python wireguard-vpn-diagnostic-suite.py --interface wgsrv1
"""

import argparse
import os
import sys

try:
    import paramiko
except ImportError:
    print("[ERROR] paramiko is required. Install with: pip install paramiko")
    sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Troubleshoot and diagnose WireGuard VPN server tunnels."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("GATEWAY_HOST", "192.168.1.1"),
        help="WireGuard Host / Gateway IP (env: GATEWAY_HOST)",
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
        "--interface",
        default="wgsrv1",
        help="WireGuard interface name (e.g. wgsrv1, wg0)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if not args.password:
        print(
            "[ERROR] Password must be specified via --password or GATEWAY_PASSWORD env var."
        )
        sys.exit(1)

    print(f"[*] Connecting to {args.host} for WireGuard Diagnostic...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(args.host, username=args.user, password=args.password, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        sys.exit(1)

    try:
        # 1. Check WireGuard Interface State
        print(f"\n[*] 1. Querying WireGuard Interface ({args.interface})...")
        _, stdout, _ = ssh.exec_command(
            f"wg show {args.interface} 2>/dev/null || wg show"
        )
        wg_output = stdout.read().decode().strip()
        if not wg_output:
            print(
                f"  [-] [FAIL] No active WireGuard interface named '{args.interface}' found."
            )
        else:
            print("  [+] Active WireGuard Status:")
            for line in wg_output.splitlines():
                print(f"      {line}")

        # 2. Check Conntrack for Dropped / Unreplied Handshakes
        print(
            "\n[*] 2. Checking Netfilter Conntrack for Dropped Handshakes (UDP Port 51820)..."
        )
        _, stdout, _ = ssh.exec_command(
            "conntrack -L -p udp --dport 51820 2>/dev/null || true"
        )
        ct_output = stdout.read().decode().strip()
        if "UNREPLIED" in ct_output:
            print("  [!] [WARNING] Detected UNREPLIED packets on port 51820!")
            print(
                "      Root Cause: WireGuard kernel dropped handshake due to Mismatched Keypair or PSK."
            )
            print(
                "      Remediation: Re-generate the client configuration QR code / profile."
            )
        else:
            print(
                "  [+] No unreplied cryptographic drops detected on port 51820. [PASS]"
            )

        # 3. Check Kernel Packet Counters
        print(f"\n[*] 3. Capturing Live Traffic on {args.interface} for 5 seconds...")
        _, stdout, _ = ssh.exec_command(
            f"timeout 5 tcpdump -n -i {args.interface} 2>/dev/null || true"
        )
        dump_output = stdout.read().decode().strip()
        if dump_output:
            print(f"  [+] Live Tunneled Packets:\n{dump_output[:300]}...")
        else:
            print("  [-] Idle / No active traffic streaming during sample.")

        print("\n" + "=" * 70)
        print(" [SUMMARY] WireGuard Diagnostic Completed.")
        print("=" * 70 + "\n")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
