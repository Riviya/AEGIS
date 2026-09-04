# Run Aegis Autonomous Incident Detection Engine (Phase 4)
param(
    [string]$Config = "configs\slos\payment-api.yaml",
    [string]$PromUrl = "http://localhost:9090",
    [string]$Window = "5m",
    [switch]$Watch,
    [switch]$Json,
    [string]$SaveReport = "",
    [switch]$FailOnIncident
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== Aegis SRE Platform — Autonomous Incident Detection Engine ===" -ForegroundColor Cyan

# Test if Prometheus is reachable
try {
    $resp = Invoke-WebRequest -Uri "$PromUrl/-/healthy" -UseBasicParsing -TimeoutSec 3
    if ($resp.StatusCode -ne 200) {
        Write-Warning "Prometheus responded with status $($resp.StatusCode)"
    }
} catch {
    Write-Warning "Prometheus is not reachable at $PromUrl."
    Write-Host "Remember to run: kubectl -n monitoring port-forward svc/prometheus 9090:9090" -ForegroundColor Yellow
}

$watchFlag = if ($Watch) { "--watch" } else { "" }
$jsonFlag = if ($Json) { "--json" } else { "" }
$failFlag = if ($FailOnIncident) { "--fail-on-incident" } else { "" }
$saveFlag = if ($SaveReport) { "--save-report `"$SaveReport`"" } else { "" }

$engineDir = Join-Path $PSScriptRoot "..\apps\aegis-engine"
$configPath = Join-Path $PSScriptRoot "..\" $Config

Push-Location $engineDir
try {
    python -m app.main --detect --slo-config "$configPath" --prom-url "$PromUrl" --window "$Window" $watchFlag $jsonFlag $failFlag $saveFlag
} finally {
    Pop-Location
}
