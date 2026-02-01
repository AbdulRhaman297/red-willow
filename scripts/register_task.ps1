<#
PowerShell helper to register/unregister the Jarvis Task Scheduler entry using the provided XML template.

Usage (run in Administrator or normal user depending on policy):
  # Register the task for the current user (no password required) using the template
  .\register_task.ps1 -Action Register

  # Unregister / remove the task
  .\register_task.ps1 -Action Unregister

Notes:
- The script will replace placeholders in 'jarvis_task_template.xml' (%%PYTHON%%, %%SCRIPT%%, %%USER%%)
- It will attempt to use Register-ScheduledTask; if unavailable, it falls back to schtasks.exe
- The task is configured to run on user logon, hidden, and set to run even on battery power
#>
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Register','Unregister','Status')]
    [string]$Action
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Template = Join-Path $ScriptDir 'jarvis_task_template.xml'
$TmpXml = Join-Path $env:TEMP 'jarvis_task_generated.xml'
$TaskName = 'Jarvis'

function Get-PythonPath {
    $py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
    if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue)?.Source }
    if (-not $py) { Write-Verbose 'Python not found on PATH'; return $null }
    return $py
}

function Register-JarvisTask {
    if (-not (Test-Path $Template)) { Write-Error "Template not found at $Template"; return }
    $python = Get-PythonPath
    if (-not $python) {
        Write-Warning "Python not found on PATH. Please pass a full python path by setting the system PATH or edit the XML template."
    }
    $scriptPath = (Resolve-Path (Join-Path $ScriptDir '..\jarvis.py')).Path
    $user = $env:USERNAME

    $xml = Get-Content $Template -Raw
    $xml = $xml -replace '%%PYTHON%%', ($python -replace '\\','\\\\')
    $xml = $xml -replace '%%SCRIPT%%', ($scriptPath -replace '\\','\\\\')
    $xml = $xml -replace '%%USER%%', $user

    $xml | Out-File -FilePath $TmpXml -Encoding Unicode

    try {
        if (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue) {
            Register-ScheduledTask -TaskName $TaskName -Xml (Get-Content $TmpXml -Raw) -Force
            Write-Host "Task '$TaskName' registered successfully (via Register-ScheduledTask)."
        } else {
            # fallback to schtasks
            $cmd = "schtasks /Create /TN `"$TaskName`" /XML `"$TmpXml`" /F"
            Write-Host "Falling back to schtasks: $cmd"
            iex $cmd
            Write-Host "Task registered via schtasks."
        }
    } catch {
        Write-Error "Failed to register task: $_"
    } finally {
        if (Test-Path $TmpXml) { Remove-Item $TmpXml -ErrorAction SilentlyContinue }
    }
}

function Unregister-JarvisTask {
    try {
        if (Get-Command Unregister-ScheduledTask -ErrorAction SilentlyContinue) {
            if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
                Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
                Write-Host "Task '$TaskName' unregistered."
            } else {
                Write-Host "Task '$TaskName' not found."
            }
        } else {
            $cmd = "schtasks /Delete /TN `"$TaskName`" /F"
            iex $cmd
            Write-Host "Task deleted via schtasks."
        }
    } catch {
        Write-Error "Failed to unregister task: $_"
    }
}

function Show-TaskStatus {
    try {
        if (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue) {
            Get-ScheduledTask -TaskName $TaskName | Format-List *
        } else {
            iex "schtasks /Query /TN `"$TaskName`" /V /FO LIST"
        }
    } catch {
        Write-Error "Could not query task status: $_"
    }
}

switch ($Action) {
    'Register' { Register-JarvisTask }
    'Unregister' { Unregister-JarvisTask }
    'Status' { Show-TaskStatus }
}
