param(
  [string]$RepoUrl = "https://github.com/akgularda/RadioTEDU",
  [string]$TargetDir = "$PWD\RadioTEDU"
)

$ErrorActionPreference = "Stop"

if (Test-Path -LiteralPath $TargetDir) {
  Set-Location -LiteralPath $TargetDir
  git pull --ff-only
} else {
  git clone $RepoUrl $TargetDir
  Set-Location -LiteralPath $TargetDir
}

if (-not (Test-Path -LiteralPath ".env") -and (Test-Path -LiteralPath ".env.example")) {
  Copy-Item ".env.example" ".env"
}

Write-Host ""
Write-Host "RadioTEDU website server starter is ready."
Write-Host "Open this prompt in Codex and execute it:"
Write-Host (Resolve-Path "handoff\web-server\prompt.md")
Write-Host ""
Get-Content -Raw "handoff\web-server\prompt.md"
