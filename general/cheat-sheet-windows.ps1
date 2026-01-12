<#
.SYNOPSIS
    A collection of administrative snippets for Windows and Exchange.
#>

# --- Event Logs ---
# Clear all event logs via PowerShell
Get-WinEvent -ListLog * | ForEach-Object { [System.Diagnostics.Eventing.Reader.EventLogSession]::GlobalSession.ClearLog($_.LogName) }

# --- Exchange Online ---
function Set-DefaultCalendarPermissions {
    param($AccessRights = "LimitedDetails")
    
    $Users = Get-Mailbox -RecipientTypeDetails UserMailbox
    foreach ($User in $Users) {
        $CalendarPath = "$($User.Alias):\Calendar"
        Write-Host "Updating permissions for $CalendarPath"
        Set-MailboxFolderPermission -Identity $CalendarPath -User Default -AccessRights $AccessRights
    }
}

# --- Service Accounts ---
# Find services running as a specific user across a list of servers
function Get-ServiceAccounts {
    param($ServerList = "Servers.txt", $AccountName = "Administrator")
    
    Get-Content $ServerList | ForEach-Object {
        $Server = $_
        Get-WmiObject Win32_Service -ComputerName $Server | Where-Object { $_.StartName -match $AccountName } | Select-Object Name, StartName, StartMode, @{N='Server';E={$Server}}
    }
}

# --- Security & Registry ---
# Disable AutoRun/AutoPlay (System-wide)
function Disable-AutoRun {
    $Paths = @("HKLM:\Software\Microsoft\Windows\CurrentVersion\policies\Explorer")
    foreach ($Path in $Paths) {
        if (-not (Test-Path $Path)) { New-Item $Path -Force }
        Set-ItemProperty $Path -Name "NoDriveTypeAutorun" -Type "DWord" -Value 0xFF
        Set-ItemProperty $Path -Name "NoAutorun" -Type "DWord" -Value 1
    }
}
