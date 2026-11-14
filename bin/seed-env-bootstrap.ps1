#!/usr/bin/env pwsh
<#
.SYNOPSIS
    SEED-AI Environment Isolation Bootstrap.

.DESCRIPTION
    Establishes the isolated SEED development environment by:
      1. Verifying the project-owned virtual environment.
      2. Running the environment isolation audit (ZKBioTime detection).
      3. Ensuring core dependencies are installed from pyproject.toml.
      4. Verifying no foreign root is resolvable by SEED's interpreter.

    This is the first script any SEED process should invoke so that
    Python resolves exclusively from D:\SEED-AI\.venv, never from
    the PATH (which contains C:\ZKBioTime, D:\ZKBioTime, B:\ZKBioTime).

.NOTES
    - Non-destructive: never modifies the ZKBioTime installations.
    - WSL/Docker are intentionally not required; SEED runs native Windows.
#>

[CmdletBinding()]
param(
    [string]$Workspace = "D:\SEED-AI"
)

$ErrorActionPreference = 'Stop'
$SeedRoot  = Resolve-Path $Workspace -ErrorAction Stop
$Venv      = Join-Path $SeedRoot ".venv"
$Python    = Join-Path $Venv "Scripts\python.exe"
$Isolation = Join-Path $SeedRoot "core\environment_isolation.py"

function Write-Step($msg)  { Write-Host "[SEED-ENV] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  WARN $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "  FAIL $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "=== SEED-AI Environment Isolation Bootstrap ===" -ForegroundColor White
Write-Host "Workspace : $($SeedRoot)"
Write-Host "Venv      : $($Venv)"
Write-Host ""

# --- Step 1: Verify virtual environment ---------------------------------------
Write-Step "[1/5] Verifying virtual environment..."
if (-not (Test-Path $Python)) {
    Write-Err "SEED interpreter not found at $Python"
    Write-Host "        Create it with: python -m venv .venv" -ForegroundColor DarkGray
    exit 1
}
$ver = & $Python --version
Write-Ok "Interpreter: $Python ($ver)"

# --- Step 2: Run isolation audit ----------------------------------------------
Write-Step "[2/5] Running environment isolation audit..."
Push-Location $SeedRoot
try {
    $env:SEED_ROOT = $SeedRoot
    $report = & $Python $Isolation audit_runtime 2>&1 | Out-String
    $reportPath = Join-Path $SeedRoot "audit_runtime.json"
    $report | Set-Content -Path $reportPath -Encoding UTF8
    Write-Ok "Audit report written to $reportPath"

    $audit = $report | ConvertFrom-Json
    if ($audit.foreign_site_packages_found.Count -eq 0) {
        Write-Ok "Zero foreign site-packages reachable."
    } else {
        Write-Err "Foreign site-packages reachable:"
        $audit.foreign_site_packages_found | ForEach-Object { Write-Host "       $_" -ForegroundColor Red }
    }
    if ($audit.loaded_foreign_modules.Count -gt 0) {
        Write-Warn "Foreign modules currently loaded into this process:"
        $audit.loaded_foreign_modules | ForEach-Object { Write-Host "       $_" -ForegroundColor Yellow }
    }
} finally {
    Pop-Location
}

# --- Step 3: Verify dependency health -----------------------------------------
Write-Step "[3/5] Verifying core dependencies..."
$deps = @("psutil", "yaml", "pytest", "mcp", "pydantic")
$missing = @()
foreach ($d in $deps) {
    $code = "import $d"
    & $Python -c $code 2>$null
    if ($LASTEXITCODE -ne 0) { $missing += $d }
}
if ($missing.Count -eq 0) {
    Write-Ok "All core dependencies import cleanly."
} else {
    Write-Warn "Missing optional deps: $($missing -join ', ')"
}

# --- Step 4: Check contamination in PATH --------------------------------------
Write-Step "[4/5] Checking PATH contamination (SEED resolves explicitly, PATH is informational)..."
$pathEntries = $env:PATH -split ';' | Where-Object { $_ -match 'ZKBioTime' }
if ($pathEntries.Count -gt 0) {
    Write-Warn "PATH contains foreign ZKBioTime entries:"
    $pathEntries | ForEach-Object { Write-Host "       $_" -ForegroundColor Yellow }
    Write-Host "        SEED is unaffected because it resolves the interpreter explicitly." -ForegroundColor DarkGray
} else {
    Write-Ok "PATH is clean of ZKBioTime."
}

# --- Step 5: Final integrity verification -------------------------------------
Write-Step "[5/5] Verifying interpreter isolation..."
$sysPathJson = & $Python -c "import sys, json; print(json.dumps(sys.path))" | ConvertFrom-Json
$contaminated = @($sysPathJson | Where-Object { $_ -match 'ZKBioTime' })
if ($contaminated.Count -gt 0) {
    Write-Err "sys.path contains ZKBioTime entries:"
    $contaminated | ForEach-Object { Write-Host "       $_" -ForegroundColor Red }
    exit 1
}
Write-Ok "sys.path is free of ZKBioTime contamination."

Write-Host ""
Write-Host "=== SEED environment isolation verified ===" -ForegroundColor Green
Write-Host ""
Write-Host "Run SEED processes using:  `$Python" -ForegroundColor DarkGray