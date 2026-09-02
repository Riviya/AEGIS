# Run Aegis SLO & Error Budget Evaluation
param(
    [string]$Config = "configs\slos\payment-api.yaml",
    [string]$PromUrl = "http://localhost:9090",
    [string]$Window = "5m",
    [switch]$Watch,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== Aegis SRE Platform — SLO & Error Budget Engine ===" -ForegroundColor Cyan

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

$engineDir = Join-Path $PSScriptRoot "..\apps\aegis-engine"
$configPath = Join-Path $PSScriptRoot "..\" $Config

Push-Location $engineDir
try {
    python -m app.main --slo-config "$configPath" --prom-url "$PromUrl" --window "$Window" $watchFlag $jsonFlag
} finally {
    Pop-Location
}
