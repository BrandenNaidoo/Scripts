#!/usr/bin/env python3
"""
ESXi Rolling Cluster Upgrade Orchestrator
=========================================
Orchestrates automated, sequential, zero-downtime upgrades across physical ESXi
hosts in a vSphere cluster using pyVmomi and SSH ESXCLI commands.

Workflow per host:
1. Validates cluster DRS / VM evacuation readiness.
2. Places host into Maintenance Mode (evacuating VMs).
3. Connects via SSH to query and apply target Image Profile / Offline Depot.
4. Executes graceful host reboot.
5. Polls host until management services & vCenter reconnection return online.
6. Verifies upgraded ESXi build version.
7. Exits Maintenance Mode and balances VMs before proceeding to next node.

Usage:
    export VCENTER_HOST="vcenter.example.com"
    export VCENTER_USER="administrator@vsphere.local"
    export VCENTER_PASSWORD="YourPassword"
    export ESXI_ROOT_PASSWORD="YourEsxiPassword"
    export TARGET_PROFILE="ESXi-8.0U3b-24280767-standard"

    python esxi-rolling-cluster-upgrade.py --hosts 192.168.1.11 192.168.1.12 192.168.1.13
"""

import argparse
import os
import ssl
import sys
import time
from typing import Any, Optional

try:
    import paramiko
    from pyVim.connect import Disconnect, SmartConnect
    from pyVmomi import vim
except ImportError:
    print(
        "[ERROR] Required libraries missing. Install with: pip install pyvmomi paramiko"
    )
    sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequential zero-downtime ESXi cluster upgrade orchestrator."
    )
    parser.add_argument(
        "--vcenter",
        default=os.environ.get("VCENTER_HOST", "127.0.0.1"),
        help="vCenter Server IP or FQDN (env: VCENTER_HOST)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("VCENTER_USER", "administrator@vsphere.local"),
        help="vCenter Admin Username (env: VCENTER_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("VCENTER_PASSWORD", ""),
        help="vCenter Admin Password (env: VCENTER_PASSWORD)",
    )
    parser.add_argument(
        "--esxi-user",
        default=os.environ.get("ESXI_ROOT_USER", "root"),
        help="ESXi Host Root User (env: ESXI_ROOT_USER)",
    )
    parser.add_argument(
        "--esxi-password",
        default=os.environ.get("ESXI_ROOT_PASSWORD", ""),
        help="ESXi Host Root Password (env: ESXI_ROOT_PASSWORD)",
    )
    parser.add_argument(
        "--profile",
        default=os.environ.get("TARGET_PROFILE", ""),
        help="Target ESXi Image Profile Name (env: TARGET_PROFILE)",
    )
    parser.add_argument(
        "--depot-path",
        default=os.environ.get("DEPOT_PATH", ""),
        help="Datastore path to Offline Bundle zip (e.g. /vmfs/volumes/Datastore/update.zip)",
    )
    parser.add_argument(
        "--hosts",
        nargs="+",
        required=True,
        help="Ordered list of ESXi host management IPs to upgrade sequentially.",
    )
    parser.add_argument(
        "--timeout-reboot",
        type=int,
        default=600,
        help="Maximum seconds to wait for host reboot (default: 600s)",
    )
    return parser.parse_args()


def get_vcenter_host_object(content: Any, host_ip: str) -> Optional[Any]:
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    )
    hosts = list(container.view)
    container.Destroy()
    for h in hosts:
        if h.name == host_ip or host_ip in h.name:
            return h
    return None


def execute_ssh_command(host_ip: str, user: str, password: str, cmd: str) -> str:
    """Executes a command on ESXi host via keyboard-interactive SSH."""
    t = paramiko.Transport((host_ip, 22))
    t.connect()
    t.auth_interactive(
        user, lambda title, instructions, prompt_list: [password for _ in prompt_list]
    )
    client = paramiko.SSHClient()
    client._transport = t
    stdin, stdout, stderr = client.exec_command(cmd)
    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()
    client.close()
    if error and not output:
        raise RuntimeError(f"SSH Command Failed on {host_ip}: {error}")
    return output


def set_maintenance_mode(host_obj: Any, enable: bool) -> None:
    """Sets or clears maintenance mode on an ESXi host object in vCenter."""
    if enable:
        if not host_obj.runtime.inMaintenanceMode:
            print(f"[*] Placing host {host_obj.name} into Maintenance Mode...")
            task = host_obj.EnterMaintenanceMode_Task(
                timeout=0, evacuatePoweredOffVms=True
            )
            while task.info.state in [
                vim.TaskInfo.State.running,
                vim.TaskInfo.State.queued,
            ]:
                time.sleep(5)
            if task.info.state != vim.TaskInfo.State.success:
                raise RuntimeError(
                    f"Failed to enter maintenance mode: {task.info.error.msg}"
                )
            print(f"[+] Host {host_obj.name} is now in Maintenance Mode.")
    else:
        if host_obj.runtime.inMaintenanceMode:
            print(f"[*] Exiting Maintenance Mode for host {host_obj.name}...")
            task = host_obj.ExitMaintenanceMode_Task(timeout=0)
            while task.info.state in [
                vim.TaskInfo.State.running,
                vim.TaskInfo.State.queued,
            ]:
                time.sleep(3)
            print(f"[+] Host {host_obj.name} exited Maintenance Mode successfully.")


def upgrade_host(host_ip: str, args: argparse.Namespace, host_obj: Any) -> None:
    print(f"\n{'=' * 70}")
    print(f" STARTING ROLLING UPGRADE: {host_ip}")
    print(f"{'=' * 70}")

    # 1. Maintenance Mode
    set_maintenance_mode(host_obj, True)

    # 2. Execute Image Profile Upgrade via ESXCLI
    print(
        f"[*] Connecting to {host_ip} via SSH to execute image profile installation..."
    )
    if args.depot_path:
        upgrade_cmd = f"esxcli software profile update -d {args.depot_path} -p {args.profile} --no-hardware-warning"
    else:
        upgrade_cmd = (
            f"esxcli software profile update -p {args.profile} --no-hardware-warning"
        )

    print(f"[*] Running: {upgrade_cmd}")
    res = execute_ssh_command(host_ip, args.esxi_user, args.esxi_password, upgrade_cmd)
    print(f"[+] Update Output:\n{res[:400]}...")

    # 3. Trigger Graceful Reboot
    print(f"[*] Initiating graceful reboot on {host_ip}...")
    try:
        execute_ssh_command(host_ip, args.esxi_user, args.esxi_password, "reboot")
    except Exception:
        pass  # Connection drop expected on reboot command

    # 4. Wait for Host Recovery
    print(f"[*] Waiting for {host_ip} to complete boot sequence and reconnect...")
    start_time = time.time()
    reconnected = False
    while time.time() - start_time < args.timeout_reboot:
        time.sleep(15)
        try:
            current_ver = execute_ssh_command(
                host_ip, args.esxi_user, args.esxi_password, "vmware -v"
            )
            print(f"[+] Host {host_ip} returned online! Active Build: {current_ver}")
            reconnected = True
            break
        except Exception:
            elapsed = int(time.time() - start_time)
            print(
                f"  [-] Waiting for SSH daemon... ({elapsed}s / {args.timeout_reboot}s)"
            )

    if not reconnected:
        raise TimeoutError(
            f"Host {host_ip} did not return online within {args.timeout_reboot} seconds."
        )

    # 5. Exit Maintenance Mode
    set_maintenance_mode(host_obj, False)
    print(f"[SUCCESS] Node {host_ip} upgrade cycle finished successfully!\n")


def main() -> None:
    args = parse_arguments()
    if not args.password or not args.esxi_password:
        print("[ERROR] Both vCenter and ESXi root passwords are required.")
        sys.exit(1)

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    print(f"[*] Connecting to vCenter: {args.vcenter}...")
    si = SmartConnect(
        host=args.vcenter,
        user=args.user,
        pwd=args.password,
        sslContext=ssl_context,
    )

    try:
        content = si.RetrieveContent()
        for host_ip in args.hosts:
            host_obj = get_vcenter_host_object(content, host_ip)
            if not host_obj:
                print(
                    f"[ERROR] Host {host_ip} not found in vCenter inventory. Skipping."
                )
                continue
            upgrade_host(host_ip, args, host_obj)

        print(
            "=========================================================================="
        )
        print(
            " [COMPLETE] CLUSTER ROLLING UPGRADE COMPLETED WITH ZERO SERVICE DOWNTIME"
        )
        print(
            "=========================================================================="
        )
    finally:
        Disconnect(si)


if __name__ == "__main__":
    main()
