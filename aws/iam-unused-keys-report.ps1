<#
.SYNOPSIS
    Identifies IAM Access Keys that haven't been used for more than 90 days.

.DESCRIPTION
    A security cleanup tool to reduce the attack surface by identifying stale credentials.
#>

[CmdletBinding()]
param (
    [int]$StaleDays = 90
)

$ThresholdDate = (Get-Date).AddDays(-$StaleDays)
$StaleKeys = [System.Collections.Generic.List[Object]]::new()

try {
    $Users = Get-IAMUser
    foreach ($User in $Users) {
        $AccessKeys = Get-IAMAccessKey -UserName $User.UserName
        foreach ($Key in $AccessKeys) {
            $LastUsed = Get-IAMAccessKeyLastUsed -AccessKeyId $Key.AccessKeyId
            
            $LastDate = $LastUsed.LastUsedDate
            if ($null -eq $LastDate) {
                # Key created but never used
                $LastDate = $Key.CreateDate
            }

            if ($LastDate -lt $ThresholdDate -and $Key.Status -eq "Active") {
                $StaleKeys.Add([PSCustomObject]@{
                    UserName    = $User.UserName
                    AccessKeyId = $Key.AccessKeyId
                    LastUsed    = $LastDate
                    DaysOld     = (New-TimeSpan -Start $LastDate -End (Get-Date)).Days
                })
            }
        }
    }
} catch {
    Write-Error "Failed to audit IAM keys: $($_.Exception.Message)"
}

if ($StaleKeys.Count -gt 0) {
    Write-Host "Identified $($StaleKeys.Count) stale IAM keys older than $StaleDays days." -ForegroundColor Red
    $StaleKeys | Sort-Object DaysOld -Descending | Format-Table
} else {
    Write-Host "No stale keys found." -ForegroundColor Green
}
