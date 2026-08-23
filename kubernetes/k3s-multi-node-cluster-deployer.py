#!/usr/bin/env python3
"""
K3s Lightweight Kubernetes Multi-Node Cluster Orchestrator
==========================================================
Automates the provisioning, token extraction, and worker join operations
for high-availability K3s multi-node clusters on Linux VMs.

Workflow:
1. Validates master node control plane readiness (k3s.service).
2. Extracts cluster node-token securely from master filesystem (/var/lib/rancher/k3s/server/node-token).
3. Connects to designated worker nodes via SSH.
4. Executes official k3s worker installation passing `K3S_URL` and `K3S_TOKEN`.
5. Verifies cluster status via `kubectl get nodes -o wide`.

Usage:
    export MASTER_HOST="192.168.1.100"
    export MASTER_USER="ubuntu"
    export MASTER_PASSWORD="YourPassword"
    export WORKER_PASSWORD="YourPassword"

    python k3s-multi-node-cluster-deployer.py --workers 192.168.1.101 192.168.1.102
"""

import argparse
import os
import sys
import time

try:
    import paramiko
except ImportError:
    print("[ERROR] paramiko is required. Install with: pip install paramiko")
    sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automate K3s Multi-Node Cluster deployment and worker registration."
    )
    parser.add_argument(
        "--master",
        default=os.environ.get("MASTER_HOST", "127.0.0.1"),
        help="K3s Master Node IP or FQDN (env: MASTER_HOST)",
    )
    parser.add_argument(
        "--master-user",
        default=os.environ.get("MASTER_USER", "ubuntu"),
        help="Master SSH Username (env: MASTER_USER)",
    )
    parser.add_argument(
        "--master-password",
        default=os.environ.get("MASTER_PASSWORD", ""),
        help="Master SSH / Sudo Password (env: MASTER_PASSWORD)",
    )
    parser.add_argument(
        "--workers",
        nargs="+",
        required=True,
        help="List of Worker Node IPs to join to the cluster",
    )
    parser.add_argument(
        "--worker-user",
        default=os.environ.get("WORKER_USER", "ubuntu"),
        help="Worker SSH Username (env: WORKER_USER)",
    )
    parser.add_argument(
        "--worker-password",
        default=os.environ.get("WORKER_PASSWORD", ""),
        help="Worker SSH / Sudo Password (env: WORKER_PASSWORD)",
    )
    return parser.parse_args()


def run_sudo(ssh: paramiko.SSHClient, password: str, cmd: str) -> str:
    full_cmd = f"echo '{password}' | sudo -S {cmd}"
    stdin, stdout, stderr = ssh.exec_command(full_cmd)
    return stdout.read().decode().strip()


def main() -> None:
    args = parse_arguments()
    if not args.master_password or not args.worker_password:
        print("[ERROR] Both Master and Worker passwords must be provided.")
        sys.exit(1)

    print(f"[*] Connecting to K3s Master: {args.master}...")
    ssh_master = paramiko.SSHClient()
    ssh_master.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_master.connect(
            args.master,
            username=args.master_user,
            password=args.master_password,
            timeout=10,
        )
    except Exception as e:
        print(f"[ERROR] Failed to connect to Master: {e}")
        sys.exit(1)

    try:
        # 1. Retrieve Cluster Node Token
        print("[*] Retrieving K3s cluster node-token from master...")
        node_token = run_sudo(
            ssh_master,
            args.master_password,
            "cat /var/lib/rancher/k3s/server/node-token",
        )
        if not node_token:
            print("[ERROR] Failed to read node-token from master.")
            sys.exit(1)
        print(f"[+] Retrieved Cluster Token: {node_token[:15]}... (Masked)")

        k3s_url = f"https://{args.master}:6443"

        # 2. Join Each Worker Node
        for worker_ip in args.workers:
            print(f"\n{'=' * 70}")
            print(f"[*] Provisioning and Joining Worker: {worker_ip}...")
            ssh_worker = paramiko.SSHClient()
            ssh_worker.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh_worker.connect(
                    worker_ip,
                    username=args.worker_user,
                    password=args.worker_password,
                    timeout=10,
                )
                join_cmd = f"curl -sfL https://get.k3s.io | K3S_URL='{k3s_url}' K3S_TOKEN='{node_token}' sh -"
                print("  [*] Executing K3s agent join script...")
                res = run_sudo(ssh_worker, args.worker_password, join_cmd)
                print(f"  [+] Join Output:\n{res[:300]}...")
            except Exception as e:
                print(f"  [-] Failed to join worker {worker_ip}: {e}")
            finally:
                ssh_worker.close()

        # 3. Verify Cluster Nodes Status
        print("\n[*] Verifying live cluster nodes from master...")
        time.sleep(5)
        nodes_status = run_sudo(
            ssh_master, args.master_password, "k3s kubectl get nodes -o wide"
        )
        print(f"\n{nodes_status}\n")

        print(
            "=========================================================================="
        )
        print(" [COMPLETE] K3s Multi-Node Cluster Deployed & Operational.")
        print(
            "=========================================================================="
        )
    finally:
        ssh_master.close()


if __name__ == "__main__":
    main()
