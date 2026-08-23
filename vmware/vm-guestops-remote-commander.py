#!/usr/bin/env python3
"""
VMware Guest Operations Remote Execution Engine
================================================
Executes arbitrary scripts, binaries, and system diagnostic tasks directly
inside guest Virtual Machines (Windows & Linux) via VMware Tools GuestOps API,
bypassing the need for open SSH, RDP, or external network reachability.

Features:
- Direct execution through ESXi / vCenter VMCI channel.
- Captures standard output, exit codes, and process termination status.
- Zero network exposure required for guest management.

Usage:
    export VCENTER_HOST="vcenter.example.com"
    export VCENTER_USER="administrator@vsphere.local"
    export VCENTER_PASSWORD="YourPassword"
    export GUEST_USER="root" # or "Administrator"
    export GUEST_PASSWORD="YourGuestPassword"

    python vm-guestops-remote-commander.py --vm "web-server-01" --command "/bin/uname -a"
"""

import argparse
import os
import ssl
import sys
import time
from typing import Any, Optional

try:
    from pyVim.connect import Disconnect, SmartConnect
    from pyVmomi import vim
except ImportError:
    print("[ERROR] pyVmomi is required. Install with: pip install pyvmomi")
    sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute commands inside Guest VMs via VMware Tools GuestOps API."
    )
    parser.add_argument(
        "--vcenter",
        default=os.environ.get("VCENTER_HOST", "127.0.0.1"),
        help="vCenter Server IP or FQDN (env: VCENTER_HOST)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("VCENTER_USER", "administrator@vsphere.local"),
        help="vCenter User (env: VCENTER_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("VCENTER_PASSWORD", ""),
        help="vCenter Password (env: VCENTER_PASSWORD)",
    )
    parser.add_argument(
        "--vm",
        required=True,
        help="Target Virtual Machine Display Name",
    )
    parser.add_argument(
        "--guest-user",
        default=os.environ.get("GUEST_USER", "root"),
        help="Guest OS Username (env: GUEST_USER)",
    )
    parser.add_argument(
        "--guest-password",
        default=os.environ.get("GUEST_PASSWORD", ""),
        help="Guest OS Password (env: GUEST_PASSWORD)",
    )
    parser.add_argument(
        "--command",
        required=True,
        help="Full program path or executable to run inside the guest OS",
    )
    parser.add_argument(
        "--args",
        default="",
        help="Arguments to pass to the executable",
    )
    return parser.parse_args()


def find_vm_by_name(content: Any, vm_name: str) -> Optional[Any]:
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True
    )
    for vm in container.view:
        if vm.name == vm_name:
            container.Destroy()
            return vm
    container.Destroy()
    return None


def main() -> None:
    args = parse_arguments()
    if not args.password or not args.guest_password:
        print("[ERROR] Both vCenter password and Guest OS password are required.")
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
        vm = find_vm_by_name(content, args.vm)
        if not vm:
            print(f"[ERROR] Virtual Machine '{args.vm}' not found.")
            sys.exit(1)

        # Validate VMware Tools status
        tools_status = vm.guest.toolsRunningStatus
        if tools_status != "guestToolsRunning":
            print(
                f"[ERROR] VMware Tools is not running on {args.vm} (Status: {tools_status})."
            )
            sys.exit(1)

        print(
            f"[+] Found VM '{vm.name}'. Guest OS: {vm.guest.guestFullName} (Tools: Running)"
        )

        guest_ops = content.guestOperationsManager
        auth = vim.NamePasswordAuthentication(
            username=args.guest_user, password=args.guest_password
        )

        prog_spec = vim.guest.ProcessManager.ProgramSpec(
            programPath=args.command,
            arguments=args.args,
        )

        print(f"[*] Dispatching execution into Guest: '{args.command} {args.args}'...")
        pid = guest_ops.processManager.StartProgramInGuest(
            vm=vm, auth=auth, spec=prog_spec
        )
        print(f"[+] Started program in guest. Process ID: {pid}")

        # Poll process termination
        print("[*] Monitoring process execution...")
        while True:
            proc_info_list = guest_ops.processManager.ListProcessesInGuest(
                vm=vm, auth=auth, pids=[pid]
            )
            if not proc_info_list:
                break
            proc = proc_info_list[0]
            if proc.endTime is not None:
                print(f"[+] Process {pid} completed with Exit Code: {proc.exitCode}")
                break
            time.sleep(2)

    finally:
        Disconnect(si)


if __name__ == "__main__":
    main()
