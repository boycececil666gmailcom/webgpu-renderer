#region Packaging
param(
    [string]$TargetApk = "bin\webgpurenderer-0.1.0-arm64-v8a-debug.apk"
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$SrcApk = Join-Path $ScriptDir $TargetApk
$SoPath = Join-Path $ScriptDir "target\aarch64-linux-android\release\libwebgpu_engine.so"
$TmpDir = Join-Path $ScriptDir "build_apk_tmp"
$ManifestXml = Join-Path $TmpDir "AndroidManifest.xml"

Write-Host "[Pack-Android] Starting pure-Rust Android NativeActivity APK packaging pipeline..."

if (-not (Test-Path $SoPath)) {
    Write-Error "[Pack-Android] Rust cdylib not found at $SoPath. Run: cargo build --target aarch64-linux-android --release"
    exit 1
}

# 1. Ensure Manifest XML exists
if (-not (Test-Path $ManifestXml)) {
    @'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
          package="org.antigravity.webgpurenderer">
    <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34"/>
    <uses-feature android:glEsVersion="0x00020000"/>
    <application android:label="WebGPU Renderer"
                 android:theme="@android:style/Theme.NoTitleBar.Fullscreen"
                 android:hasCode="false">
        <activity android:name="android.app.NativeActivity"
                  android:label="WebGPU Renderer"
                  android:configChanges="orientation|keyboardHidden|screenSize"
                  android:exported="true">
            <meta-data android:name="android.app.lib_name" android:value="webgpu_engine"/>
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
'@ | Set-Content -Path $ManifestXml -Encoding UTF8
}

# 2. Compile binary AndroidManifest.xml via aapt2 in WSL
$wslManifest = ($ManifestXml -replace "\\", "/") -replace "C:", "/mnt/c"
wsl -d Ubuntu-22.04 -- aapt2 link -I /usr/share/android-framework-res/framework-res.apk --manifest $wslManifest -o /home/boyce/test_manifest.apk
wsl -d Ubuntu-22.04 -- bash -c "unzip -p /home/boyce/test_manifest.apk AndroidManifest.xml > /home/boyce/binary_manifest.xml"
$binaryManifestPath = Join-Path $TmpDir "binary_manifest.xml"
wsl -d Ubuntu-22.04 -- bash -c "cp /home/boyce/binary_manifest.xml /mnt/c/Users/boyce/OneDrive/Desktop/webgpu-renderer/build_apk_tmp/binary_manifest.xml"

# 3. Assemble zip
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

# Add assets
Add-FileToZip -zipArchive $zip -entryName "assets/shaders/shader.wgsl" -filePath (Join-Path $ScriptDir "shaders\shader.wgsl")
Add-FileToZip -zipArchive $zip -entryName "assets/.env" -filePath (Join-Path $ScriptDir ".env")
Add-FileToZip -zipArchive $zip -entryName "assets/gltf/mclaren_p1.glb" -filePath (Join-Path $ScriptDir "gltf\mclaren_p1.glb")

$zip.Dispose()
$zipStream.Close()

# 4. Zipalign via WSL
Write-Host "[Pack-Android] Aligning APK..."
$wslUnsigned = ($UnsignedApk -replace "\\", "/") -replace "C:", "/mnt/c"
$wslAligned = ($AlignedApk -replace "\\", "/") -replace "C:", "/mnt/c"
wsl -d Ubuntu-22.04 -- zipalign -f -p 4 $wslUnsigned $wslAligned

# 5. Sign via WSL apksigner
Write-Host "[Pack-Android] Signing APK..."
$wslFinal = ($FinalApk -replace "\\", "/") -replace "C:", "/mnt/c"
wsl -d Ubuntu-22.04 -- apksigner sign --ks /home/boyce/.android/debug.keystore --ks-pass pass:android --key-pass pass:android --ks-key-alias androiddebugkey --out $wslFinal $wslAligned

# Copy to target APK
$destDir = Split-Path $SrcApk -Parent
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
}
Copy-Item -Path $FinalApk -Destination $SrcApk -Force
Write-Host "[Pack-Android] SUCCESS: Pure-Rust NativeActivity APK ready at $SrcApk"
#endregion
