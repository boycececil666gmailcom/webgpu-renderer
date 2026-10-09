#region BuildPipeline
param(
    [string]$Configuration = "release"
)

$ErrorActionPreference = "Stop"
$WindowsDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $WindowsDir "..")).Path

Write-Host "[Build-Windows] Starting Windows native build pipeline ($Configuration)..."

$cargoArgs = @("build")
if ($Configuration -eq "release") {
    $cargoArgs += "--release"
}

Push-Location $ProjectRoot
try {
    Write-Host "[Build-Windows] Compiling Rust host executable via Cargo..."
    & cargo @cargoArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Error "[Build-Windows] Compilation failed with exit code $LASTEXITCODE."
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

$ExePath = Join-Path $ProjectRoot "target\$Configuration\webgpu-renderer.exe"
if (Test-Path $ExePath) {
    Write-Host "[Build-Windows] SUCCESS: Windows executable ready at $ExePath"
    Write-Host "[Build-Windows] To launch, run: powershell -ExecutionPolicy Bypass -File .\windows\run.ps1"
} else {
    Write-Error "[Build-Windows] Expected executable not found at $ExePath"
    exit 1
}
#endregion
