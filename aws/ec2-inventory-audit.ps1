<#
.SYNOPSIS
    Generates a CSV report of all EC2 instances and their basic configuration.

.DESCRIPTION
    Uses the AWS Tools for PowerShell to audit instances across regions.
    Identifies instance types, states, and missing tags.

.PARAMETER Regions
    Array of AWS regions to scan. Defaults to all available regions.
#>

[CmdletBinding()]
param (
    [string[]]$Regions = (Get-AWSRegion).Region
)

$Results = [System.Collections.Generic.List[Object]]::new()

foreach ($Region in $Regions) {
    Write-Host "Scanning Region: $Region" -ForegroundColor Yellow
    try {
        $Instances = Get-EC2Instance -Region $Region
        foreach ($Reservation in $Instances) {
            foreach ($Instance in $Reservation.Instances) {
                $NameTag = ($Instance.Tags | Where-Object { $_.Key -eq "Name" }).Value
                
                $Obj = [PSCustomObject]@{
                    Region        = $Region
                    InstanceId    = $Instance.InstanceId
                    Name          = $NameTag
                    InstanceType  = $Instance.InstanceType
                    State         = $Instance.State.Name
                    PublicIp      = $Instance.PublicIpAddress
                    PrivateIp     = $Instance.PrivateIpAddress
                    LaunchTime    = $Instance.LaunchTime
                }
                $Results.Add($Obj)
            }
        }
    } catch {
        Write-Warning "Could not scan region $Region : $($_.Exception.Message)"
    }
}

if ($Results.Count -gt 0) {
    $Path = ".\EC2_Inventory_$((Get-Date -Format 'yyyyMMdd')).csv"
    $Results | Export-Csv -Path $Path -NoTypeInformation
    Write-Host "Inventory exported to: $Path" -ForegroundColor Green
} else {
    Write-Host "No instances found." -ForegroundColor Gray
}
