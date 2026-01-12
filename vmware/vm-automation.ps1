<#
.SYNOPSIS
    Automated vSphere host patching and maintenance utility.

.DESCRIPTION
    Scans, remediates, and manages maintenance mode for ESXi hosts.
    Supports critical patches and version upgrades.

.PARAMETER vCenter
    The FQDN or IP of the vCenter server.

.PARAMETER ClusterName
    The name of the cluster containing the host.

.PARAMETER VMHost
    The FQDN of the ESXi host to patch.

.EXAMPLE
    ./vm-automation.ps1 -vCenter "vcenter.domain.local" -VMHost "esx01.domain.local"
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]$vCenter,

    [Parameter(Mandatory=$false)]
    [string]$VMHost,

    [string]$BaselineName = "*Critical*"
)

try {
    # Initialize PowerCLI
    if (!(Get-Module -Name VMware.VimAutomation.Core -ErrorAction SilentlyContinue)) {
        Import-Module VMware.VimAutomation.Core -ErrorAction Stop
    }

    # Connect to vCenter
    Write-Host "Connecting to $vCenter..." -ForegroundColor Cyan
    Connect-VIServer -Server $vCenter -ErrorAction Stop

    if ($null -eq $VMHost) {
        Write-Host "No host specified. Listing available hosts..." -ForegroundColor Yellow
        Get-VMHost | Select-Object Name, ConnectionState, PowerState
        return
    }

    $TargetHost = Get-VMHost -Name $VMHost -ErrorAction Stop

    # 1. Compliance Scan
    Write-Host "Scanning $VMHost for compliance..." -ForegroundColor Yellow
    $Scan = Test-Compliance -Entity $TargetHost
    Get-Compliance -Entity $TargetHost | Format-Table -AutoSize

    # 2. Maintenance Mode
    Write-Host "Entering Maintenance Mode..." -ForegroundColor Yellow
    Set-VMHost -VMHost $TargetHost -State Maintenance -Evacuate -Confirm:$false

    # 3. Patching
    Write-Host "Deploying patches matching '$BaselineName'..." -ForegroundColor Green
    $Baselines = Get-PatchBaseline -Name $BaselineName
    foreach ($Baseline in $Baselines) {
        Update-Entity -Entity $TargetHost -Baseline $Baseline -Confirm:$false
    }

    # 4. Exit Maintenance Mode
    Write-Host "Exiting Maintenance Mode..." -ForegroundColor Green
    Set-VMHost -VMHost $TargetHost -State Connected

    Write-Host "Patching process for $VMHost complete." -ForegroundColor Green

} catch {
    Write-Error "VMware Automation Error: $($_.Exception.Message)"
} finally {
    if ($DefaultVIServers) {
        Disconnect-VIServer -Server $vCenter -Confirm:$false
    }
}