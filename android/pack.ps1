#region Packaging
param(
    [string]$TargetApk = ""
)

$ErrorActionPreference = "Stop"
$AndroidDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $AndroidDir "..")).Path

if (-not $TargetApk) {
    $TargetApk = Join-Path $ProjectRoot "bin\webgpurenderer-0.1.0-arm64-v8a-debug.apk"
}

$SoPath = Join-Path $ProjectRoot "target\aarch64-linux-android\release\libwebgpu_engine.so"
$TmpDir = Join-Path $AndroidDir ".tmp"
$ManifestXml = Join-Path $AndroidDir "AndroidManifest.xml"

Write-Host "[Pack-Android] Packaging pure-Rust NativeActivity APK..."

if (-not (Test-Path $SoPath)) {
    Write-Error "[Pack-Android] Rust cdylib not found at $SoPath. Run build.ps1 first."
    exit 1
}

if (-not (Test-Path $TmpDir)) {
    New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
}

# 1. Compile binary AndroidManifest.xml via aapt2 in WSL
$wslManifest = ($ManifestXml -replace "\\", "/") -replace "C:", "/mnt/c"
$wslTmpDir = ($TmpDir -replace "\\", "/") -replace "C:", "/mnt/c"

wsl -d Ubuntu-22.04 -- aapt2 link -I /usr/share/android-framework-res/framework-res.apk --manifest $wslManifest -o "$wslTmpDir/manifest.apk"
wsl -d Ubuntu-22.04 -- bash -c "unzip -p $wslTmpDir/manifest.apk AndroidManifest.xml > $wslTmpDir/binary_manifest.xml"
$binaryManifestPath = Join-Path $TmpDir "binary_manifest.xml"

# 2. Assemble APK archive
$UnsignedApk = Join-Path $TmpDir "unsigned.apk"
$AlignedApk = Join-Path $TmpDir "aligned.apk"
$FinalApk = Join-Path $TmpDir "final.apk"

if (Test-Path $UnsignedApk) { Remove-Item $UnsignedApk -Force }
if (Test-Path $AlignedApk) { Remove-Item $AlignedApk -Force }
if (Test-Path $FinalApk) { Remove-Item $FinalApk -Force }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zipStream = [System.IO.File]::Open($UnsignedApk, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite)
$zip = New-Object System.IO.Compression.ZipArchive($zipStream, [System.IO.Compression.ZipArchiveMode]::Create)

function Add-FileToZip([System.IO.Compression.ZipArchive]$zipArchive, [string]$entryName, [string]$filePath) {
    if (Test-Path $filePath) {
        $entry = $zipArchive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
        $stream = $entry.Open()
        $bytes = [System.IO.File]::ReadAllBytes($filePath)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Close()
        Write-Host "[Pack-Android] Added entry: $entryName ($( [math]::Round($bytes.Length / 1KB, 1) ) KB)"
    }
}

# Add binary manifest
Add-FileToZip -zipArchive $zip -entryName "AndroidManifest.xml" -filePath $binaryManifestPath

# Add Rust cdylib
Add-FileToZip -zipArchive $zip -entryName "lib/arm64-v8a/libwebgpu_engine.so" -filePath $SoPath

# Add shaders and assets
Add-FileToZip -zipArchive $zip -entryName "assets/shaders/shader.wgsl" -filePath (Join-Path $ProjectRoot "shaders\shader.wgsl")
Add-FileToZip -zipArchive $zip -entryName "assets/.env" -filePath (Join-Path $ProjectRoot ".env")
Add-FileToZip -zipArchive $zip -entryName "assets/gltf/mclaren_p1.glb" -filePath (Join-Path $ProjectRoot "gltf\mclaren_p1.glb")

$zip.Dispose()
$zipStream.Close()

# 3. Zipalign via WSL
Write-Host "[Pack-Android] Aligning APK..."
$wslUnsigned = ($UnsignedApk -replace "\\", "/") -replace "C:", "/mnt/c"
$wslAligned = ($AlignedApk -replace "\\", "/") -replace "C:", "/mnt/c"
wsl -d Ubuntu-22.04 -- zipalign -f -p 4 $wslUnsigned $wslAligned

# 4. Sign via WSL apksigner
Write-Host "[Pack-Android] Signing APK..."
$wslFinal = ($FinalApk -replace "\\", "/") -replace "C:", "/mnt/c"
wsl -d Ubuntu-22.04 -- apksigner sign --ks /home/boyce/.android/debug.keystore --ks-pass pass:android --key-pass pass:android --ks-key-alias androiddebugkey --out $wslFinal $wslAligned

# 5. Output to target path
$destDir = Split-Path $TargetApk -Parent
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
}
Copy-Item -Path $FinalApk -Destination $TargetApk -Force
Write-Host "[Pack-Android] SUCCESS: APK generated at $TargetApk"
#endregion
