# Enterprise Automation Scripts

A curated collection of production-grade automation scripts for Active Directory, AWS, VMware, and Windows Server environments. Designed for security, scalability, and ease of use.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PowerShell Analysis](https://github.com/BrandenNaidoo/Scripts/actions/workflows/powershell-analysis.yml/badge.svg)](https://github.com/BrandenNaidoo/Scripts/actions)

## Repository Structure

### Active Directory
*   **monitor-inactive-users.ps1**: Identifies and reports on stale computer and user accounts.
*   **notify-password-expiry.ps1**: Branded HTML email notifications for upcoming password expirations.

### AWS (Cloud Infrastructure)
*   **ec2-inventory-audit.ps1**: Multi-region inventory reporting for EC2 instances.
*   **iam-unused-keys-report.ps1**: Security audit tool to find and report stale IAM access keys.

### VMware
*   **vm-automation.ps1**: Modular utility for host patching and maintenance mode orchestration.

### SQL Server
*   **recover-sysadmin-access.ps1**: Emergency recovery tool to grant sysadmin rights via SYSTEM task elevation.

### Windows Server
*   **rds-cleanup.ps1**: Safe, profile-aware cleanup of temporary files and browser caches.

### General & Documentation
*   **cheat-sheet-linux.md**: Essential CLI snippets for Linux sysadmins.
*   **cheat-sheet-windows.ps1**: Reusable PowerShell functions for common admin tasks.

## Standards & Best Practices

All scripts in this repository follow these enterprise standards:
*   **No Hardcoding**: Configuration is handled via Parameters.
*   **Error Handling**: Comprehensive Try/Catch blocks for graceful failures.
*   **Documentation**: Help blocks (.SYNOPSIS) included in every script.
*   **Non-Interactive**: Designed for scheduling via RMM or Task Scheduler.

## Usage

Example: Running the Active Directory Monitor
```powershell
./active-directory/monitor-inactive-users.ps1 -DaysInactive 90 -SMTPServer "smtp.email.co.za"
```

## Disclaimer

These scripts are provided as-is. Always review code before running it in a production environment. Measure twice, cut once.

## License

This project is licensed under the MIT License.
