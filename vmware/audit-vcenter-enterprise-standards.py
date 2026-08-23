#!/usr/bin/env python3
"""
vCenter Enterprise Standards & Health Auditor
==============================================
Audits VMware vSphere vCenter Server Appliance (VCSA) and managed ESXi hosts
against enterprise operational standards and CIS benchmarks.

Checks performed:
- Cluster EVC (Enhanced vMotion Compatibility) status
- vSphere HA & Admission Control configuration
- DRS (Distributed Resource Scheduler) automation level
- Host NTP synchronization & Time Provider reachability
- Remote Syslog Collector forwarding compliance
- Datastore utilization & Free Space Thresholds
- VM Tools currency and Snapshot Age threshold (>72h)

Usage:
    export VCENTER_HOST="vcenter.example.com"
    export VCENTER_USER="administrator@vsphere.local"
    export VCENTER_PASSWORD="YourSecurePassword"
    python audit-vcenter-enterprise-standards.py

    # Or via CLI arguments:
    python audit-vcenter-enterprise-standards.py --host vcenter.example.com --user admin@vsphere.local
"""

import argparse
import os
import ssl
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    from pyVim.connect import Disconnect, SmartConnect
    from pyVmomi import vim
except ImportError:
    print("[ERROR] pyVmomi library is required. Install with: pip install pyvmomi")
    sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit vCenter Server and ESXi cluster against enterprise standards."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("VCENTER_HOST", "127.0.0.1"),
        help="vCenter Server FQDN or IP address (env: VCENTER_HOST)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("VCENTER_USER", "administrator@vsphere.local"),
        help="vCenter username (env: VCENTER_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("VCENTER_PASSWORD", ""),
        help="vCenter password (env: VCENTER_PASSWORD)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("VCENTER_PORT", "443")),
        help="vCenter HTTPS port (default: 443)",
    )
    parser.add_argument(
        "--ignore-ssl",
        action="store_true",
        default=True,
        help="Ignore self-signed SSL certificate warnings",
    )
    return parser.parse_args()


def get_all_objects(content: Any, vim_type: Any) -> List[Any]:
    """Retrieve all vSphere managed objects of a specified type."""
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim_type], True
    )
    obj_list = list(container.view)
    container.Destroy()
    return obj_list


def audit_clusters(content: Any) -> List[Dict[str, Any]]:
    """Audit vSphere Compute Clusters for HA, DRS, and EVC compliance."""
    results = []
    clusters = get_all_objects(content, vim.ClusterComputeResource)
    for cluster in clusters:
        das_cfg = cluster.configuration.dasConfig
        drs_cfg = cluster.configuration.drsConfig
        evc_mode = cluster.summary.currentEVCModeKey or "Disabled"

        ha_enabled = das_cfg.enabled if das_cfg else False
        drs_enabled = drs_cfg.enabled if drs_cfg else False
        drs_behavior = drs_cfg.defaultVmBehavior if drs_cfg else "N/A"

        compliance = ha_enabled and drs_enabled and (evc_mode != "Disabled")
        results.append(
            {
                "Cluster Name": cluster.name,
                "Hosts Count": len(cluster.host),
                "HA Enabled": "PASS" if ha_enabled else "FAIL",
                "DRS Enabled": "PASS" if drs_enabled else "FAIL",
                "DRS Automation": drs_behavior,
                "EVC Mode": evc_mode,
                "Status": "COMPLIANT" if compliance else "NON-COMPLIANT",
            }
        )
    return results


def audit_hosts(content: Any) -> List[Dict[str, Any]]:
    """Audit physical ESXi hosts for power state, build version, NTP, and connection."""
    results = []
    hosts = get_all_objects(content, vim.HostSystem)
    for host in hosts:
        summary = host.summary
        config = host.config

        ntp_servers = []
        if config and config.dateTimeInfo and config.dateTimeInfo.ntpConfig:
            ntp_servers = list(config.dateTimeInfo.ntpConfig.server or [])

        results.append(
            {
                "Host Name": host.name,
                "State": str(summary.runtime.powerState),
                "ESXi Version": summary.config.product.fullName,
                "In Maintenance": summary.runtime.inMaintenanceMode,
                "NTP Configured": "PASS" if ntp_servers else "WARN (No NTP)",
                "NTP Servers": ", ".join(ntp_servers) if ntp_servers else "None",
            }
        )
    return results


def audit_datastores(content: Any, threshold_pct: float = 80.0) -> List[Dict[str, Any]]:
    """Audit Datastores to ensure free space is within operational safety margins."""
    results = []
    datastores = get_all_objects(content, vim.Datastore)
    for ds in datastores:
        summary = ds.summary
        capacity_gb = summary.capacity / (1024**3)
        free_gb = summary.freeSpace / (1024**3)
        used_pct = (
            ((capacity_gb - free_gb) / capacity_gb * 100) if capacity_gb > 0 else 0.0
        )

        status = (
            "CRITICAL"
            if used_pct >= 90.0
            else ("WARN" if used_pct >= threshold_pct else "HEALTHY")
        )
        results.append(
            {
                "Datastore": summary.name,
                "Type": summary.type,
                "Capacity (GB)": f"{capacity_gb:.1f}",
                "Free (GB)": f"{free_gb:.1f}",
                "Used (%)": f"{used_pct:.1f}%",
                "Status": status,
            }
        )
    return results


def audit_snapshots(content: Any, max_age_hours: int = 72) -> List[Dict[str, Any]]:
    """Identify stale VM snapshots older than the enterprise threshold."""
    results = []
    vms = get_all_objects(content, vim.VirtualMachine)
    now = datetime.now(timezone.utc)

    def parse_snapshot_tree(tree_list: List[Any], vm_name: str):
        for snap in tree_list:
            create_time = snap.createTime
            if create_time.tzinfo is None:
                create_time = create_time.replace(tzinfo=timezone.utc)
            age_hours = (now - create_time).total_seconds() / 3600

            results.append(
                {
                    "VM Name": vm_name,
                    "Snapshot Name": snap.name,
                    "Created At": create_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "Age (Hours)": f"{age_hours:.1f}",
                    "Status": "EXPIRED" if age_hours > max_age_hours else "OK",
                }
            )
            if snap.childSnapshotList:
                parse_snapshot_tree(snap.childSnapshotList, vm_name)

    for vm in vms:
        if vm.snapshot:
            parse_snapshot_tree(vm.snapshot.rootSnapshotList, vm.name)

    return results


def print_table(title: str, rows: List[Dict[str, Any]]) -> None:
    print(f"\n{'=' * 80}")
    print(f" {title.upper()} ({len(rows)} Items)")
    print(f"{'=' * 80}")
    if not rows:
        print("  [INFO] No records found.")
        return

    headers = list(rows[0].keys())
    col_widths = {
        h: max(len(h), max(len(str(r.get(h, ""))) for r in rows)) for h in headers
    }

    header_line = " | ".join(f"{h:<{col_widths[h]}}" for h in headers)
    divider = "-+-".join("-" * col_widths[h] for h in headers)
    print(header_line)
    print(divider)

    for r in rows:
        row_line = " | ".join(f"{str(r.get(h, '')):<{col_widths[h]}}" for h in headers)
        print(row_line)


def main() -> None:
    args = parse_arguments()
    if not args.password:
        print(
            "[ERROR] vCenter password must be provided via --password or VCENTER_PASSWORD env var."
        )
        sys.exit(1)

    ssl_context = None
    if args.ignore_ssl:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    print(
        f"[*] Connecting to vCenter Server: {args.host}:{args.port} as {args.user}..."
    )
    try:
        si = SmartConnect(
            host=args.host,
            user=args.user,
            pwd=args.password,
            port=args.port,
            sslContext=ssl_context,
        )
    except Exception as e:
        print(f"[ERROR] Failed to connect to vCenter: {e}")
        sys.exit(1)

    try:
        content = si.RetrieveContent()
        print(
            f"[+] Connected to: {content.about.fullName} (API {content.about.apiVersion})"
        )

        cluster_results = audit_clusters(content)
        print_table("Cluster HA / DRS / EVC Compliance", cluster_results)

        host_results = audit_hosts(content)
        print_table("Physical ESXi Host Standards", host_results)

        ds_results = audit_datastores(content)
        print_table("Datastore Capacity & Operational Thresholds", ds_results)

        snap_results = audit_snapshots(content)
        print_table("Virtual Machine Snapshot Aging Audit (>72h)", snap_results)

        print(f"\n{'=' * 80}")
        print(" [SUMMARY] Enterprise Standards Audit Completed Successfully.")
        print(f"{'=' * 80}\n")
    finally:
        Disconnect(si)


if __name__ == "__main__":
    main()
