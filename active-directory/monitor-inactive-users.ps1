<#
.SYNOPSIS
    Monitors and reports on inactive AD computers and users.
    
.DESCRIPTION
    Identifies objects that haven't logged in for a specified period, 
    exports them to CSV, and optionally emails the report.
    It can also disable and move identified objects to a staging OU.

.PARAMETER DaysInactive
    The number of days an account must be inactive to be flagged. Default is 60.

.PARAMETER SearchBase
    The Distinguished Name of the OU to search within.

.PARAMETER SMTPServer
    The SMTP server to use for sending reports.

.PARAMETER EmailFrom
    The sender email address for the report.

.PARAMETER EmailTo
    The recipient email address for the report.

.EXAMPLE
    ./monitor-inactive-users.ps1 -DaysInactive 90 -SearchBase "OU=Users,DC=domain,DC=local"
#>

[CmdletBinding()]
param (
    [int]$DaysInactive = 60,
    [string]$SearchBase = (Get-ADDomain).DistinguishedName,
    [string]$SMTPServer = "EmailServer",
    [string]$EmailFrom = "admin@domain.com",
    [string]$EmailTo = "admin@domain.com",
    [string]$ReportPath = ".\InActive_Report_$((Get-Date -Format 'yyyyMMdd')).csv"
)

try {
    Write-Verbose "Initializing Active Directory module..."
    Import-Module ActiveDirectory -ErrorAction Stop

    $CutoffDate = (Get-Date).AddDays(-$DaysInactive)
    Write-Host "Searching for objects inactive since: $($CutoffDate.ToShortDateString())" -ForegroundColor Cyan

    # --- Computer Report ---
    Write-Host "Processing Inactive Computers..." -ForegroundColor Yellow
    $InactiveComputers = Get-ADComputer -Filter {LastLogonTimestamp -lt $CutoffDate} -SearchBase $SearchBase -Properties Name, LastLogonTimestamp
    $ComputerReport = $InactiveComputers | Select-Object Name, @{N='LastLogon'; E={[DateTime]::FromFileTime($_.LastLogonTimestamp)}}
    
    # --- User Report ---
    Write-Host "Processing Inactive Users..." -ForegroundColor Yellow
    $InactiveUsers = Get-ADUser -Filter {LastLogonTimestamp -lt $CutoffDate} -SearchBase $SearchBase -Properties Name, LastLogonTimestamp
    $UserReport = $InactiveUsers | Select-Object Name, @{N='LastLogon'; E={[DateTime]::FromFileTime($_.LastLogonTimestamp)}}

    # Combine and Export
    $FinalReport = $ComputerReport + $UserReport
    if ($FinalReport) {
        $FinalReport | Export-Csv -Path $ReportPath -NoTypeInformation
        Write-Host "Report generated: $ReportPath" -ForegroundColor Green

        # Optional Emailing
        if ($SMTPServer -ne "EmailServer") {
            Send-MailMessage -From $EmailFrom -To $EmailTo -Port 587 -SMTPServer $SMTPServer -Subject "Inactive Objects Report - $DaysInactive Days" -Attachment $ReportPath -Body "Attached is the report for inactive users and computers."
            Write-Host "Email sent to $EmailTo" -ForegroundColor Green
        }
    } else {
        Write-Host "No inactive objects found." -ForegroundColor Gray
    }

} catch {
    Write-Error "An error occurred during AD scan: $($_.Exception.Message)"
}