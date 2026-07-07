param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$LiquidsoapCommand = $env:LIQUIDSOAP_COMMAND,
    [string]$LiquidsoapScript = $env:LIQUIDSOAP_SCRIPT
)

function Get-DotEnvValue {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $key, $value = $trimmed.Split("=", 2)
        if ($key.Trim() -eq $Name) {
            return $value.Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

$envPath = Join-Path $ProjectRoot ".env"
if (-not $LiquidsoapCommand) {
    $LiquidsoapCommand = Get-DotEnvValue -Path $envPath -Name "LIQUIDSOAP_COMMAND"
}
if (-not $LiquidsoapCommand) {
    $LiquidsoapCommand = Get-DotEnvValue -Path $envPath -Name "LIQUIDSOAP_PATH"
}
if (-not $LiquidsoapCommand) {
    $LiquidsoapCommand = "liquidsoap"
}
if (-not $LiquidsoapScript) {
    $LiquidsoapScript = Get-DotEnvValue -Path $envPath -Name "LIQUIDSOAP_SCRIPT"
}
if (-not $LiquidsoapScript) {
    $LiquidsoapScript = Get-DotEnvValue -Path $envPath -Name "LIQUIDSOAP_SCRIPT_PATH"
}
if (-not $LiquidsoapScript) {
    $LiquidsoapScript = "liquidsoap/radiotedu.liq"
}

$scriptPath = if ([IO.Path]::IsPathRooted($LiquidsoapScript)) { $LiquidsoapScript } else { Join-Path $ProjectRoot $LiquidsoapScript }
if (-not (Test-Path -LiteralPath $scriptPath)) {
    Push-Location $ProjectRoot
    try {
        python -c "from backend.config import Settings; from backend.liquidsoap import render_liquidsoap_config; print(render_liquidsoap_config(Settings.from_env()))"
    }
    finally {
        Pop-Location
    }
}
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Liquidsoap script was not found or rendered: $scriptPath"
}

Write-Host "Starting Liquidsoap with $scriptPath"
Start-Process -FilePath $LiquidsoapCommand -ArgumentList @($scriptPath) -WorkingDirectory $ProjectRoot -WindowStyle Hidden
