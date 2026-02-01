<#
PowerShell helper to list audio input devices and set the Jarvis default microphone.

Features:
- Lists available audio input devices (friendly names)
- Lets user pick a device number to set as Jarvis default (stores JARVIS_MIC_NAME in .env)
- Attempts to set the system default microphone via the AudioDeviceCmdlets module if available

Usage:
  Run in PowerShell (not necessarily admin):
    .\set_default_mic.ps1

Notes:
- To set the system default device automatically, install the AudioDeviceCmdlets module:
    Install-Module -Name AudioDeviceCmdlets -Scope CurrentUser
  Then this script will call Set-AudioDevice to set the system default (if present).
- If the module isn't available, the script will still save the chosen mic name to .env so Jarvis will try to use it.
#>

function Get-InputDevices {
    # Prefer using AudioDeviceCmdlets if available for richer names
    if (Get-Module -ListAvailable -Name AudioDeviceCmdlets) {
        Import-Module AudioDeviceCmdlets -ErrorAction SilentlyContinue
        try {
            return Get-AudioDevice -List | Where-Object { $_.Type -eq "Capture" } | Select-Object @{n='Name';e={$_.Name}}, @{n='Id';e={$_.Id}}, @{n='Index';e={$_.Index}}
        } catch {
            Write-Verbose "AudioDeviceCmdlets present but failed enumerating; falling back"
        }
    }

    # Fallback: use CIM/Win32_SoundDevice (less granular)
    $devs = Get-CimInstance Win32_SoundDevice | Select-Object Name, DeviceID
    return $devs
}

function Write-EnvKey($key, $value) {
    $repo = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
    $envfile = Join-Path $repo ".env"
    if (-not (Test-Path $envfile)) { New-Item -Path $envfile -ItemType File -Force | Out-Null }
    $text = Get-Content $envfile -Raw
    if ($text -match "^$key=") {
        $text = ($text -split "`n" | ForEach-Object { if ($_ -match "^$key=") { "$key=$value" } else { $_ } }) -join "`n"
    } else {
        $text = $text + "`n$key=$value`n"
    }
    $text | Set-Content $envfile -Encoding UTF8
    Write-Host "Saved $key to $envfile"
}

# MAIN
$devices = Get-InputDevices
if (-not $devices) {
    Write-Warning "No audio input devices found. Make sure microphone is plugged in and drivers are installed."
    exit 1
}

Write-Host "Available audio input devices:" -ForegroundColor Cyan
$idx = 0
foreach ($d in $devices) {
    $idx++
    if ($d.PSObject.Properties.Name -contains 'Index') {
        $i = $d.Index
    } else {
        $i = $idx
    }
    $name = $d.Name
    Write-Host "[$idx] $name"
}

$sel = Read-Host "Enter the number of the device to set as Jarvis default"
if (-not [int]::TryParse($sel, [ref]$null)) {
    Write-Warning "Invalid selection"
    exit 2
}
$sel = [int]$sel
if ($sel -lt 1 -or $sel -gt $devices.Count) {
    Write-Warning "Selection out of range"
    exit 2
}
$choice = $devices[$sel - 1]
$devname = $choice.Name
Write-Host "Selected: $devname" -ForegroundColor Green

# Attempt to set system default if AudioDeviceCmdlets available
if (Get-Module -ListAvailable -Name AudioDeviceCmdlets) {
    try {
        Import-Module AudioDeviceCmdlets -ErrorAction Stop
        if ($choice.PSObject.Properties.Name -contains 'Index') {
            Write-Host "Setting system default capture device by Index: $($choice.Index)"
            Set-AudioDevice -Index $choice.Index -AsDefault -Direction Capture -ErrorAction Stop
        } else {
            Write-Host "Setting system default capture device by Name"
            Set-AudioDevice -Name "$devname" -AsDefault -Direction Capture -ErrorAction Stop
        }
        Write-Host "System default capture device set to: $devname" -ForegroundColor Green
    } catch {
        Write-Warning "Failed to set system default via AudioDeviceCmdlets: $_. Saving choice to .env instead."
    }
} else {
    Write-Host "AudioDeviceCmdlets not installed; skipping system default set (will save to .env)."
}

# Save into repo .env so Jarvis will try to use it
Write-EnvKey -key 'JARVIS_MIC_NAME' -value $devname
Write-Host "Done. Jarvis will attempt to use microphone: $devname" -ForegroundColor Cyan
