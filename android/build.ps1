#region BuildPipeline
param(
    [string]$Configuration = "release",
    [switch]$SkipRustBuild
)

$ErrorActionPreference = "Stop"
$AndroidDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $AndroidDir "..")).Path

Write-Host "[Build-Android] Starting Android native build pipeline ($Configuration)..."

if (-not $SkipRustBuild) {
    Write-Host "[Build-Android] Compiling Rust cdylib for target aarch64-linux-android..."
    $cargoArgs = @("build", "--target", "aarch64-linux-android")
    if ($Configuration -eq "release") {
        $cargoArgs += "--release"
    }

    Push-Location $ProjectRoot
    try {
        & cargo @cargoArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Error "[Build-Android] Cargo compilation failed."
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }
}

Write-Host "[Build-Android] Running APK packaging..."
& powershell -ExecutionPolicy Bypass -File (Join-Path $AndroidDir "pack.ps1")

if ($LASTEXITCODE -eq 0) {
    Write-Host "[Build-Android] SUCCESS! To deploy to your Android device, run:"
    Write-Host "powershell -ExecutionPolicy Bypass -File .\android\deploy.ps1"
} else {
    Write-Error "[Build-Android] Packaging failed with exit code $LASTEXITCODE"
}
#endregion
