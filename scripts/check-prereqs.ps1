#Requires -Version 5.1
<#
.SYNOPSIS
  Checks Phase 1 tools on Windows.

.DESCRIPTION
  Prints PASS/FAIL for Docker daemon, kubectl, kind, Helm, Git.
  Docker Desktop may be installed but not running - this script reports that clearly.
#>

$ErrorActionPreference = "Continue"
$failed = 0

function Show-Result {
    param([string]$Name, [bool]$Ok, [string]$Detail)
    if ($Ok) {
        Write-Host "PASS  $Name  $Detail"
    } else {
        Write-Host "FAIL  $Name  $Detail"
        $script:failed++
    }
}

Write-Host "Aegis Phase 1 prerequisite check"
Write-Host "--------------------------------"

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Show-Result "Docker daemon" $true "docker is running"
    } else {
        Show-Result "Docker daemon" $false "Docker CLI exists but the engine is not running. Start Docker Desktop, wait until it is idle, then re-run this script."
    }
} else {
    Show-Result "Docker daemon" $false "docker not found. Install Docker Desktop with the WSL2 backend."
}

$kubectl = Get-Command kubectl -ErrorAction SilentlyContinue
if ($kubectl) {
    $v = kubectl version --client --short 2>$null
    if (-not $v) { $v = (kubectl version --client) | Select-Object -First 1 }
    Show-Result "kubectl" $true "$v"
} else {
    Show-Result "kubectl" $false "Install kubectl (Docker Desktop usually includes it)."
}

$kind = Get-Command kind -ErrorAction SilentlyContinue
if (-not $kind) {
    $kindGuesses = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\kind.exe"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Kubernetes.kind_Microsoft.Winget.Source_8wekyb3d8bbwe\kind.exe")
    )
    foreach ($kindGuess in $kindGuesses) {
        if (Test-Path $kindGuess) {
            $kind = Get-Item $kindGuess
            break
        }
    }
}
if ($kind) {
    $kv = & kind version 2>$null
    Show-Result "kind" $true "$kv"
} else {
    Show-Result "kind" $false "Install with: winget install Kubernetes.kind"
}

$helm = Get-Command helm -ErrorAction SilentlyContinue
if ($helm) {
    $hv = helm version --short 2>$null
    Show-Result "Helm" $true "$hv"
} else {
    Show-Result "Helm" $false "Install Helm 3+ (winget install Helm.Helm)."
}

$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    Show-Result "Git" $true (git --version)
} else {
    Show-Result "Git" $false "Install Git for Windows."
}

Write-Host "--------------------------------"
if ($failed -gt 0) {
    Write-Host "Result: $failed check(s) failed. Fix those before creating the kind cluster."
    exit 1
}
Write-Host "Result: all checks passed. You can create the kind cluster (see docs/PHASE1.md)."
exit 0
