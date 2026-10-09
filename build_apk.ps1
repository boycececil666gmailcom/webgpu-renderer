#region BuildPipeline
Write-Host "[Build-Android] Packaging Android APK..."
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\pack_apk.ps1"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[Build-Android] Build succeeded! To deploy wirelessly, run:"
    Write-Host "powershell -ExecutionPolicy Bypass -File .\wireless_debug\deploy.ps1"
} else {
    Write-Host "[Build-Android] Build failed with exit code $LASTEXITCODE"
}
#endregion
