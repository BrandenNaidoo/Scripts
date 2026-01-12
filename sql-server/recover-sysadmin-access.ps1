<#
.SYNOPSIS
    Emergency SQL Server Sysadmin recovery script.

.DESCRIPTION
    Uses a temporary Windows Scheduled Task running as SYSTEM to grant
    Sysadmin privileges to a specified Windows account. 
    This is useful for recovering access when SA credentials are lost.

.PARAMETER Username
    The Windows account (Domain\User) to grant sysadmin rights to.

.PARAMETER Instance
    The SQL Server instance name. Default is local.
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]$Username,

    [string]$Instance = "localhost"
)

$TaskName = "SQL_Sysadmin_Recovery"
$SqlCmd = "sqlcmd -E -S $Instance -Q ""IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = '$Username') CREATE LOGIN [$Username] FROM WINDOWS; ALTER SERVER ROLE sysadmin ADD MEMBER [$Username];"""

try {
    Write-Host "Creating temporary recovery task for $Username..." -ForegroundColor Cyan
    
    # Create the action
    $Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $SqlCmd"
    
    # Create the principal (SYSTEM)
    $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
    
    # Register and Start the task
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Principal $Principal -Force
    Start-Sleep -s 2
    Start-ScheduledTask -TaskName $TaskName
    
    Write-Host "Task executed. Please check SQL Server access for $Username." -ForegroundColor Green
    
    # Cleanup
    Start-Sleep -s 5
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

} catch {
    Write-Error "Failed to execute recovery: $($_.Exception.Message)"
}
