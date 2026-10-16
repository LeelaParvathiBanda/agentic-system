# Allows phones and other laptops on the same hotspot/LAN to reach FastAPI on TCP 8000.
# The server asks for the administrator password only the first time (-RegisterTask).
# Later starts run this script through a saved elevated task, with no password prompt.
param(
    [switch]$RegisterTask
)

$ErrorActionPreference = "Stop"
$taskName = "SmartTicketAgentLAN"

try {
    Get-NetFirewallRule -DisplayName "python.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.Action -eq "Block" } |
        Disable-NetFirewallRule
} catch {
    Write-Warning $_.Exception.Message
}

$ruleName = "Smart Ticket Agent FastAPI 8000"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existing) {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort 8000 `
        -Profile Any `
        -Description "Allow phone/LAN access to the Smart Ticket Management Agentic System FastAPI server" | Out-Null
} else {
    Set-NetFirewallRule -DisplayName $ruleName -Enabled True -Action Allow -Profile Any
}

Get-NetConnectionProfile | ForEach-Object {
    try {
        Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private
    } catch {
        Write-Warning $_.Exception.Message
    }
}

if ($RegisterTask) {
    $scriptPath = $PSCommandPath
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""
    $userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null
    Write-Host "Administrator approval saved. Later server starts will not ask for the password."
}

$stampDir = Join-Path $env:LOCALAPPDATA "SmartTicketAgent"
New-Item -ItemType Directory -Force -Path $stampDir | Out-Null
Set-Content -Path (Join-Path $stampDir "lan_access_stamp.txt") -Value (Get-Date -Format o)

Write-Host "LAN access enabled for TCP 8000."
Get-NetConnectionProfile | Select-Object Name, NetworkCategory | Format-Table -AutoSize
