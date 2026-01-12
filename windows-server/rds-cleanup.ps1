<#
.SYNOPSIS
    Maintenance script to clean up temporary files and browser caches on RDS servers.

.DESCRIPTION
    Safely removes temporary files for all user profiles to free up disk space.
    Targets Windows temp, Local AppData temp, and common browser caches.

.PARAMETER DryRun
    If true, list files to be deleted without actually removing them.
#>

[CmdletBinding()]
param (
    [switch]$DryRun
)

$TargetPaths = @(
    "AppData\Local\Temp\*",
    "AppData\Local\Mozilla\Firefox\Profiles\*.default\cache2\entries\*",
    "AppData\Local\Google\Chrome\User Data\Default\Cache\*"
)

$UserProfiles = Get-ChildItem -Path "C:\Users" -Directory

foreach ($Profile in $UserProfiles) {
    if ($Profile.Name -match "Public|Default|All Users") { continue }
    
    Write-Host "Processing Profile: $($Profile.Name)" -ForegroundColor Cyan
    
    foreach ($SubPath in $TargetPaths) {
        $FullPath = Join-Path -Path $Profile.FullName -ChildPath $SubPath
        
        if (Test-Path $FullPath) {
            Write-Verbose "Cleaning: $FullPath"
            if ($DryRun) {
                Write-Host "[DRY RUN] Would delete items in: $FullPath" -ForegroundColor Gray
            } else {
                try {
                    Remove-Item -Path $FullPath -Recurse -Force -ErrorAction SilentlyContinue
                } catch {
                    Write-Warning "Could not fully clean $FullPath"
                }
            }
        }
    }
}

# System level cleanup
$SystemTemp = "C:\Windows\Temp\*"
if (Test-Path $SystemTemp) {
    if ($DryRun) {
        Write-Host "[DRY RUN] Would clean System Temp"
    } else {
        Remove-Item -Path $SystemTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Cleanup Task Completed." -ForegroundColor Green