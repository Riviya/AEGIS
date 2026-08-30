<#
.SYNOPSIS
    Generates synthetic HTTP traffic against payment-api (directly or through WSO2 Gateway).

.DESCRIPTION
    This script sends a configurable number of requests to generate live RED telemetry
    (Rate, Errors, Duration) for Prometheus and Grafana evaluation in Aegis Phase 2.

.PARAMETER Url
    The endpoint to send requests to (default: http://localhost:18080/payments).
    To test via WSO2 Gateway: https://localhost:8243/payments/1.0.0/payments

.PARAMETER Token
    Optional Bearer token for authenticated WSO2 Gateway requests.

.PARAMETER Requests
    Total number of requests to send (default: 50).

.PARAMETER DelayMs
    Delay between consecutive requests in milliseconds (default: 50).

.EXAMPLE
    .\scripts\generate-traffic.ps1 -Requests 100
    .\scripts\generate-traffic.ps1 -Url "https://localhost:8243/payments/1.0.0/payments" -Token "YOUR_WSO2_TOKEN" -Requests 100
#>

[CmdletBinding()]
param(
    [string]$Url = "http://localhost:18080/payments",
    [string]$Token = "",
    [int]$Requests = 50,
    [int]$DelayMs = 50
)

# Disable SSL certificate validation for self-signed WSO2 local certs
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Aegis Phase 2 - Live Traffic Generator" -ForegroundColor Cyan
Write-Host " Target URL: $Url" -ForegroundColor White
Write-Host " Total Requests: $Requests | Delay: $($DelayMs)ms" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan

$successCount = 0
$errorCount = 0
$otherCount = 0
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

$headers = @{}
if ($Token -ne "") {
    $headers["Authorization"] = "Bearer $Token"
}

for ($i = 1; $i -le $Requests; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $Url -Headers $headers -Method GET -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        $statusCode = [int]$response.StatusCode
    }
    catch {
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        else {
            $statusCode = 0
        }
    }

    if ($statusCode -ge 200 -and $statusCode -lt 300) {
        $successCount++
        Write-Host "[$i/$Requests] Status: $statusCode (OK)" -ForegroundColor Green
    }
    elseif ($statusCode -ge 500) {
        $errorCount++
        Write-Host "[$i/$Requests] Status: $statusCode (Server Error)" -ForegroundColor Red
    }
    else {
        $otherCount++
        Write-Host "[$i/$Requests] Status: $statusCode" -ForegroundColor Yellow
    }

    if ($DelayMs -gt 0) {
        Start-Sleep -Milliseconds $DelayMs
    }
}

$stopwatch.Stop()
$totalSeconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 2)
$actualRps = if ($totalSeconds -gt 0) { [Math]::Round($Requests / $totalSeconds, 2) } else { 0 }
$errorRate = if ($Requests -gt 0) { [Math]::Round(($errorCount / $Requests) * 100, 2) } else { 0 }
$errorColor = if ($errorRate -gt 0) { "Red" } else { "Green" }

Write-Host ""
Write-Host "-------------------- Traffic Summary --------------------" -ForegroundColor Cyan
Write-Host " Total Requests Sent : $Requests" -ForegroundColor White
Write-Host " Successful (2xx)    : $successCount" -ForegroundColor Green
Write-Host " Errors (5xx)        : $errorCount" -ForegroundColor Red
Write-Host " Other Status Codes  : $otherCount" -ForegroundColor Yellow
Write-Host " Error Rate (%)      : $errorRate %" -ForegroundColor $errorColor
Write-Host (" Elapsed Time        : {0}s ({1} RPS)" -f $totalSeconds, $actualRps) -ForegroundColor White
Write-Host "---------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Telemetry is now recorded in Prometheus! Check your Grafana dashboard." -ForegroundColor Cyan
