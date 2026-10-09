#region RunPipeline
param(
    [string]$Configuration = "release",
    [string]$Backend = "Auto",
    [switch]$BuildFirst
)

$ErrorActionPreference = "Stop"
$WindowsDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $WindowsDir "..")).Path

if ($BuildFirst) {
    Write-Host "[Run-Windows] Building target before launching..."
    & powershell -ExecutionPolicy Bypass -File (Join-Path $WindowsDir "build.ps1") -Configuration $Configuration
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$ExePath = Join-Path $ProjectRoot "target\$Configuration\webgpu-renderer.exe"

if (-not (Test-Path $ExePath)) {
    Write-Host "[Run-Windows] Binary not found at $ExePath. Triggering build..."
    & powershell -ExecutionPolicy Bypass -File (Join-Path $WindowsDir "build.ps1") -Configuration $Configuration
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($Backend -eq "Dx12") {
    $env:WGPU_BACKEND = "dx12"
} elseif ($Backend -eq "Vulkan") {
    $env:WGPU_BACKEND = "vulkan"
} else {
    Remove-Item Env:\WGPU_BACKEND -ErrorAction SilentlyContinue
}

Write-Host "[Run-Windows] Launching $ExePath (Backend: $Backend)..."
Push-Location $ProjectRoot
try {
    & $ExePath
} finally {
    Pop-Location
}
#endregion
