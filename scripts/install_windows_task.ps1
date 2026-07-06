param(
    [string]$ProjectRoot = "F:\RTAI\RadioTEDU",
    [string]$TaskName = "RadioTEDU Forever",
    [switch]$WithFrontend
)

$ErrorActionPreference = "Stop"

$python = (Get-Command python -ErrorAction Stop).Source
$runner = Join-Path $ProjectRoot "scripts\run_station_forever.py"
$arguments = "`"$runner`" --root `"$ProjectRoot`""

if ($WithFrontend) {
    $arguments = "$arguments --frontend"
}

$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Keep RadioTEDU running locally." -Force
Write-Host "Registered scheduled task '$TaskName' for $ProjectRoot"
