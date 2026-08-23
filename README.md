# Enterprise Automation & Infrastructure Scripts

A curated collection of production-grade automation scripts for Active Directory, AWS, VMware vSphere, K3s Kubernetes, Cloudflare Zero Trust, UniFi Firewalls, and Managed SIEM environments. Designed for security, scalability, and ease of use.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PowerShell Analysis](https://github.com/BrandenNaidoo/Scripts/actions/workflows/powershell-analysis.yml/badge.svg)](https://github.com/BrandenNaidoo/Scripts/actions)

---

## 📂 Repository Structure

### 🏛️ VMware vSphere & ESXi Automation (`vmware/`)
*   **`audit-vcenter-enterprise-standards.py`**: Comprehensive auditor validating cluster EVC, HA/DRS admission control, NTP synchronization, datastore utilization, and snapshot aging (>72h).
*   **`esxi-rolling-cluster-upgrade.py`**: Zero-downtime rolling maintenance mode, image profile upgrade, and reboot orchestrator for physical ESXi clusters.
*   **`vm-guestops-remote-commander.py`**: Direct command and binary execution inside Guest VMs (Windows/Linux) via VMware Tools GuestOps API without requiring SSH/RDP.
*   **`vm-automation.ps1`**: Modular PowerShell utility for host patching and maintenance mode orchestration.

### ☸️ Kubernetes & K3s Cluster Automation (`kubernetes/`)
*   **`k3s-multi-node-cluster-deployer.py`**: Automated multi-node K3s cluster deployment, HA token extraction, and worker join orchestration.

### 🛡️ Networking & UniFi Firewall Security (`networking-firewall/`)
*   **`unifi-gateway-health-and-audit.py`**: Security and health audit of UniFi Cloud Gateway (storage capacity, logrotate, conntrack table utilization, and VLAN routing).
*   **`wireguard-vpn-diagnostic-suite.py`**: End-to-end troubleshooting tool for WireGuard VPN tunnels (handshake validation, cryptographic keypair matching, and conntrack drops).

### ☁️ Cloudflare Zero Trust & Secure Access (`cloudflare-zerotrust/`)
*   **`cloudflare-service-token-ssh-automation.py`**: Configures non-interactive, headless SSH over Cloudflare Access using Service Tokens for CI/CD runners and scripts.

### 🚨 Managed SIEM & Security Operations (`security-siem/`)
*   **`huntress-linux-siem-deployer.py`**: Automated deployment of Huntress Managed SIEM on Linux, port 514 UDP unbinding, and live spool verification.

### 🏢 Active Directory (`active-directory/`)
*   **`monitor-inactive-users.ps1`**: Identifies and reports on stale computer and user accounts.
*   **`notify-password-expiry.ps1`**: Branded HTML email notifications for upcoming password expirations.

### ☁️ AWS Cloud Infrastructure (`aws/`)
*   **`ec2-inventory-audit.ps1`**: Multi-region inventory reporting for EC2 instances.
*   **`iam-unused-keys-report.ps1`**: Security audit tool to find and report stale IAM access keys.

### 🗄️ SQL Server (`sql-server/`)
*   **`recover-sysadmin-access.ps1`**: Emergency recovery tool to grant sysadmin rights via SYSTEM task elevation.

### 💻 Windows Server (`windows-server/`)
*   **`rds-cleanup.ps1`**: Safe, profile-aware cleanup of temporary files and browser caches.

### 📖 General & Documentation (`general/`)
*   **`cheat-sheet-linux.md`**: Essential CLI snippets for Linux sysadmins.
*   **`cheat-sheet-windows.ps1`**: Reusable PowerShell functions for common admin tasks.

---

## 🔒 Security Standards & Best Practices

All scripts in this repository adhere to strict enterprise security standards:
*   **Zero Hardcoding / Zero PII**: All credentials, tokens, and endpoints are parameterized via Environment Variables or CLI arguments.
*   **Error Handling**: Comprehensive exception handling with informative error logging.
*   **Non-Interactive Execution**: Designed for headless execution via Task Scheduler, RMM, or CI/CD pipelines.

---

## 📜 License

This project is licensed under the MIT License.
