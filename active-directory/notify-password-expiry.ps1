<#
.SYNOPSIS
    Notifies users via email when their Active Directory password is about to expire.

.DESCRIPTION
    Scans enabled users with expiring passwords and sends a branded HTML email reminder.

.PARAMETER ThresholdDays
    Number of days before expiry to start notifying. Default is 14.

.PARAMETER SMTPServer
    SMTP Relay server.

.PARAMETER EmailFrom
    Sender address for the notification.

.PARAMETER SupportEmail
    Email address for the support desk included in the message body.
#>

[CmdletBinding()]
param (
    [int]$ThresholdDays = 14,
    [string]$SMTPServer = "EmailServer",
    [string]$EmailFrom = "it-notify@domain.com",
    [string]$SupportEmail = "support@domain.com"
)

try {
    Import-Module ActiveDirectory -ErrorAction Stop
    $DomainPolicy = Get-ADDefaultDomainPasswordPolicy
    $MaxPasswordAge = $DomainPolicy.MaxPasswordAge
    $Today = Get-Date

    $Users = Get-ADUser -Filter {Enabled -eq $true -and PasswordNeverExpires -eq $false} -Properties PasswordLastSet, EmailAddress, Name

    foreach ($User in $Users) {
        if ($null -eq $User.PasswordLastSet -or $null -eq $User.EmailAddress) { continue }

        $ExpiryDate = $User.PasswordLastSet + $MaxPasswordAge
        $DaysRemaining = (New-TimeSpan -Start $Today -End $ExpiryDate).Days

        if ($DaysRemaining -le $ThresholdDays -and $DaysRemaining -ge 0) {
            Write-Host "Notifying $($User.Name) ($DaysRemaining days left)" -ForegroundColor Cyan
            
            $Subject = "Security Notice: Password expires in $DaysRemaining days"
            $Body = @"
<html>
<body style='font-family: Arial, sans-serif;'>
    <h2 style='color: #d9534f;'>Password Expiry Reminder</h2>
    <p>Dear $($User.Name),</p>
    <p>Your network password is set to expire in <strong>$DaysRemaining days</strong>.</p>
    <p>Please update your password as soon as possible to avoid a lockout.</p>
    <hr>
    <h3>Password Requirements:</h3>
    <ul>
        <li>Minimum 12 characters</li>
        <li>1 Uppercase, 1 Lowercase, 1 Number</li>
        <li>1 Special Character (~!@#$%^&*)</li>
    </ul>
    <p>Need help? Contact us at <a href='mailto:$SupportEmail'>$SupportEmail</a>.</p>
    <p>Regards,<br>IT Infrastructure Team</p>
</body>
</html>
"@

            if ($SMTPServer -ne "EmailServer") {
                Send-MailMessage -SmtpServer $SMTPServer -Port 587 -To $User.EmailAddress -From $EmailFrom -Subject $Subject -Body $Body -BodyAsHtml
            } else {
                Write-Warning "SMTP Server not configured. Skipping email send for $($User.Name)."
            }
        }
    }
} catch {
    Write-Error "Failed to process password notifications: $($_.Exception.Message)"
}
