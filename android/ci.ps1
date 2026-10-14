#region Config
param(
    [switch]$SkipRustBuild,
    [string]$Configuration = "release",
    [string]$AvdName = "WebGPU_API34",
    [int]$LogDurationSeconds = 15,
    [switch]$Headless,
    [switch]$EmulatorOnly,
    [switch]$BuildOnly,
    [switch]$DeployOnly,
    [string]$Subfolder = "logs"
)

$ErrorActionPreference = "Continue"
$AndroidDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $AndroidDir "..")).Path
$Package = "org.antigravity.webgpurenderer"
$Activity = "android.app.NativeActivity"
#endregion

#region Scaffolding
$JavaHome = if ($env:JAVA_HOME) { $env:JAVA_HOME } elseif (Test-Path "C:\Users\boyce\android_sdk\JDK21\jdk-21.0.11+10") { "C:\Users\boyce\android_sdk\JDK21\jdk-21.0.11+10" } else { "" }
$AndroidHome = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif (Test-Path "C:\Users\boyce\android_sdk\Sdk") { "C:\Users\boyce\android_sdk\Sdk" } else { "" }

$Script:Adb = Join-Path $AndroidHome "platform-tools\adb.exe"
$Script:Emulator = Join-Path $AndroidHome "emulator\emulator.exe"
$Script:AvdManager = Join-Path $AndroidHome "cmdline-tools\latest\bin\avdmanager.bat"
$Script:Aapt2 = Join-Path $AndroidHome "build-tools\36.0.0\aapt2.exe"
$Script:AndroidJar = Join-Path $AndroidHome "platforms\android-36\android.jar"
$Script:Zipalign = Join-Path $AndroidHome "build-tools\36.0.0\zipalign.exe"
$Script:Apksigner = Join-Path $AndroidHome "build-tools\36.0.0\apksigner.bat"
$Script:KeystorePath = Join-Path $env:USERPROFILE ".android\debug.keystore"

$Script:TargetSerial = ""
$Script:LogSubfolder = ""
$Script:CiLogFile = ""
$Script:LogcatFile = ""

function Initialize-Environment {
    Write-Host "[CI-Init] Configuring SDK and JDK toolchain paths..."
    if ($JavaHome) {
        $env:JAVA_HOME = $JavaHome
        $env:PATH = "$JavaHome\bin;$env:PATH"
    }
    if ($AndroidHome) {
        $env:ANDROID_HOME = $AndroidHome
        $env:ANDROID_SDK_ROOT = $AndroidHome
        $env:PATH = "$AndroidHome\platform-tools;$AndroidHome\emulator;$AndroidHome\cmdline-tools\latest\bin;$AndroidHome\build-tools\36.0.0;$env:PATH"
    }
    if (Test-Path "C:\Users\boyce\.cargo\bin") {
        $env:PATH = "C:\Users\boyce\.cargo\bin;$env:PATH"
    }
}

function Initialize-Directories {
    $Script:LogSubfolder = Join-Path $AndroidDir $Subfolder
    if (-not (Test-Path $Script:LogSubfolder)) {
        New-Item -ItemType Directory -Path $Script:LogSubfolder -Force | Out-Null
    }
    $timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
    $Script:CiLogFile = Join-Path $Script:LogSubfolder "ci_$timestamp.log"
    $Script:LogcatFile = Join-Path $Script:LogSubfolder "logcat_$timestamp.log"
    Start-Transcript -Path $Script:CiLogFile -Append | Out-Null
    Write-Host "[CI-Init] Pipeline session log: $Script:CiLogFile"
    Write-Host "[CI-Init] App logcat log: $Script:LogcatFile"
}

function Invoke-Build {
    Write-Host "[CI-Build] Preparing application compilation ($Configuration)..."
    $SoPath = Join-Path $ProjectRoot "target\aarch64-linux-android\release\libwebgpu_engine.so"
    if (-not $SkipRustBuild) {
        $cargoCmd = Get-Command cargo -ErrorAction SilentlyContinue
        if (-not $cargoCmd -and (Test-Path "$env:USERPROFILE\.cargo\bin\cargo.exe")) {
            $cargoCmd = "$env:USERPROFILE\.cargo\bin\cargo.exe"
        }
        if ($cargoCmd) {
            Write-Host "[CI-Build] Compiling Rust cdylib for target aarch64-linux-android..."
            $cargoArgs = @("build", "--target", "aarch64-linux-android")
            if ($Configuration -eq "release") { $cargoArgs += "--release" }
            Push-Location $ProjectRoot
            try {
                & $cargoCmd @cargoArgs
                if ($LASTEXITCODE -ne 0) {
                    if (Test-Path $SoPath) {
                        Write-Warning "[CI-Build] Cargo compilation failed (NDK linker not configured). Falling back to existing cdylib: $SoPath"
                    } else {
                        throw "[CI-Build] Cargo compilation failed and no existing cdylib found at $SoPath."
                    }
                }
            } finally {
                Pop-Location
            }
        } elseif (Test-Path $SoPath) {
            Write-Host "[CI-Build] Cargo not located in environment; utilizing existing cdylib."
        } else {
            throw "[CI-Build] Cargo not found and no precompiled cdylib found at $SoPath."
        }
    }
}

function Invoke-Package {
    Write-Host "[CI-Pack] Packaging native APK via native Android SDK build-tools..."
    $TargetApk = Join-Path $ProjectRoot "bin\webgpurenderer-0.1.0-arm64-v8a-debug.apk"
    $SoPath = Join-Path $ProjectRoot "target\aarch64-linux-android\release\libwebgpu_engine.so"
    $TmpDir = Join-Path $AndroidDir ".tmp"
    $ManifestXml = Join-Path $AndroidDir "AndroidManifest.xml"

    if (-not (Test-Path $SoPath)) {
        throw "[CI-Pack] Rust cdylib not found at $SoPath. Build must succeed first."
    }
    if (-not (Test-Path $TmpDir)) {
        New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
    }

    # 1. Compile binary AndroidManifest.xml
    $manifestApk = Join-Path $TmpDir "manifest.apk"
    & $Script:Aapt2 link -I $Script:AndroidJar --manifest $ManifestXml -o $manifestApk
    if ($LASTEXITCODE -ne 0) { throw "[CI-Pack] aapt2 link failed." }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $binaryManifestPath = Join-Path $TmpDir "binary_manifest.xml"
    $manifestZip = [System.IO.Compression.ZipFile]::OpenRead($manifestApk)
    $entry = $manifestZip.GetEntry("AndroidManifest.xml")
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $binaryManifestPath, $true)
    $manifestZip.Dispose()

    # 2. Assemble APK archive
    $UnsignedApk = Join-Path $TmpDir "unsigned.apk"
    $AlignedApk = Join-Path $TmpDir "aligned.apk"
    $FinalApk = Join-Path $TmpDir "final.apk"

    if (Test-Path $UnsignedApk) { Remove-Item $UnsignedApk -Force }
    if (Test-Path $AlignedApk) { Remove-Item $AlignedApk -Force }
    if (Test-Path $FinalApk) { Remove-Item $FinalApk -Force }

    $zipStream = [System.IO.File]::Open($UnsignedApk, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite)
    $zip = New-Object System.IO.Compression.ZipArchive($zipStream, [System.IO.Compression.ZipArchiveMode]::Create)

    function Add-FileToArchive([System.IO.Compression.ZipArchive]$zipArchive, [string]$entryName, [string]$filePath) {
        if (Test-Path $filePath) {
            $e = $zipArchive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
            $s = $e.Open()
            $bytes = [System.IO.File]::ReadAllBytes($filePath)
            $s.Write($bytes, 0, $bytes.Length)
            $s.Close()
            Write-Host "[CI-Pack] Added: $entryName ($( [math]::Round($bytes.Length / 1KB, 1) ) KB)"
        }
    }

    Add-FileToArchive -zipArchive $zip -entryName "AndroidManifest.xml" -filePath $binaryManifestPath
    Add-FileToArchive -zipArchive $zip -entryName "lib/arm64-v8a/libwebgpu_engine.so" -filePath $SoPath
    Add-FileToArchive -zipArchive $zip -entryName "assets/shaders/shader.wgsl" -filePath (Join-Path $ProjectRoot "shaders\shader.wgsl")
    Add-FileToArchive -zipArchive $zip -entryName "assets/.env" -filePath (Join-Path $ProjectRoot ".env")
    Add-FileToArchive -zipArchive $zip -entryName "assets/gltf/mclaren_p1.glb" -filePath (Join-Path $ProjectRoot "gltf\mclaren_p1.glb")

    $zip.Dispose()
    $zipStream.Close()

    # 3. Zipalign
    Write-Host "[CI-Pack] Aligning APK..."
    & $Script:Zipalign -f -p 4 $UnsignedApk $AlignedApk
    if ($LASTEXITCODE -ne 0) { throw "[CI-Pack] zipalign failed." }

    # 4. Sign
    Write-Host "[CI-Pack] Signing APK..."
    & $Script:Apksigner sign --ks $Script:KeystorePath --ks-pass pass:android --key-pass pass:android --ks-key-alias androiddebugkey --out $FinalApk $AlignedApk
    if ($LASTEXITCODE -ne 0) { throw "[CI-Pack] apksigner failed." }

    # 5. Output
    $destDir = Split-Path $TargetApk -Parent
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    Copy-Item -Path $FinalApk -Destination $TargetApk -Force
    Write-Host "[CI-Pack] SUCCESS: Signed APK ready at $TargetApk"
}

function Ensure-Emulator {
    Write-Host "[CI-Emulator] Checking device availability..."
    & $Script:Adb start-server | Out-Null
    $devices = & $Script:Adb devices -l
    $activeEmus = @($devices | Where-Object { $_ -match "^(emulator-\d+)\s+device\b" } | ForEach-Object { ($_.Trim() -split "\s+")[0] })
    
    if ($activeEmus.Count -gt 0) {
        $Script:TargetSerial = $activeEmus[0]
        Write-Host "[CI-Emulator] Found active running emulator: $Script:TargetSerial"
        return
    }

    # Verify or create AVD
    $avdPath = Join-Path $env:USERPROFILE ".android\avd\$AvdName.avd"
    if (-not (Test-Path $avdPath)) {
        Write-Host "[CI-Emulator] AVD '$AvdName' not found. Creating virtual device..."
        "no" | & $Script:AvdManager create avd -n $AvdName -k "system-images;android-34;google_apis;x86_64" --device "pixel_6" --force
        $avdIniPath = Join-Path $avdPath "config.ini"
        if (Test-Path $avdIniPath) {
            $content = Get-Content $avdIniPath
            $content += "hw.gpu.enabled=yes`nhw.gpu.mode=host`nhw.ramSize=4096`nvm.heapSize=512"
            Set-Content -Path $avdIniPath -Value $content
        }
    } else {
        Write-Host "[CI-Emulator] Verified existing AVD configuration: $avdPath"
    }

    $existingEmu = Get-Process emulator -ErrorAction SilentlyContinue
    if (-not $existingEmu) {
        Write-Host "[CI-Emulator] Launching emulator '$AvdName' with Vulkan host acceleration..."
        $emuArgs = "-avd $AvdName -gpu host -accel on -feature Vulkan -no-snapshot-load"
        if ($Headless) { $emuArgs += " -no-window" }

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Script:Emulator
        $psi.Arguments = $emuArgs
        $psi.UseShellExecute = $true
        $psi.CreateNoWindow = $false
        [System.Diagnostics.Process]::Start($psi) | Out-Null
    } else {
        Write-Host "[CI-Emulator] Emulator process already active (PID: $($existingEmu.Id[0]))."
    }

    Write-Host "[CI-Emulator] Waiting for ADB device attachment..."
    & $Script:Adb wait-for-device

    Write-Host "[CI-Emulator] Waiting for sys.boot_completed signal..."
    $booted = $false
    for ($i = 0; $i -lt 90; $i++) {
        $rawStatus = try {
            $prevEAP = $ErrorActionPreference
            $ErrorActionPreference = "SilentlyContinue"
            $res = & $Script:Adb shell getprop sys.boot_completed 2>$null
            $ErrorActionPreference = $prevEAP
            "$res".Trim()
        } catch {
            ""
        }
        if ($rawStatus -eq "1") {
            $booted = $true
            break
        }
        Start-Sleep -Seconds 2
    }

    if (-not $booted) {
        throw "[CI-Emulator] Boot timeout exceeded waiting for emulator."
    }

    $activeNow = @((& $Script:Adb devices) | Where-Object { $_ -match "^(\S+)\s+device\b" } | ForEach-Object { ($_.Trim() -split "\s+")[0] })
    if ($activeNow.Count -eq 0) { throw "[CI-Emulator] Device not reachable after boot." }
    $Script:TargetSerial = $activeNow[0]
    Write-Host "[CI-Emulator] Target emulator ready: $Script:TargetSerial"
}

function Invoke-Deploy {
    $apk = (Get-ChildItem -Path (Join-Path $ProjectRoot "bin") -Filter "*.apk" -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    if (-not $apk) {
        throw "[CI-Deploy] No target APK detected in bin/ directory."
    }

    Write-Host "[CI-Deploy] Installing $(Split-Path $apk -Leaf) on $Script:TargetSerial..."
    $installOutput = & $Script:Adb -s $Script:TargetSerial install -r $apk 2>&1
    $installOutput | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0 -or ($installOutput -match "INSTALL_FAILED_UPDATE_INCOMPATIBLE")) {
        Write-Host "[CI-Deploy] Reinstalling package cleanly..."
        & $Script:Adb -s $Script:TargetSerial uninstall $Package | Out-Null
        & $Script:Adb -s $Script:TargetSerial install $apk
    }

    $gltfModel = Join-Path $ProjectRoot "gltf\mclaren_p1.glb"
    if (Test-Path $gltfModel) {
        Write-Host "[CI-Deploy] Syncing 3D asset mclaren_p1.glb to device storage..."
        & $Script:Adb -s $Script:TargetSerial shell mkdir -p "/sdcard/Android/data/$Package/files" | Out-Null
        & $Script:Adb -s $Script:TargetSerial push $gltfModel "/sdcard/Android/data/$Package/files/mclaren_p1.glb" | Out-Null
    }
}

function Stream-Logs {
    Write-Host "[CI-Stream] Starting $Package..."
    & $Script:Adb -s $Script:TargetSerial logcat -c
    & $Script:Adb -s $Script:TargetSerial shell am start -n "$Package/$Activity" | Out-Null

    $filter = "WebGpuEngine:* RustStdoutStderr:* AndroidRuntime:* CRASH:* DEBUG:* *:F"
    Write-Host "[CI-Stream] Recording application logs to $Script:LogcatFile..."

    if ($LogDurationSeconds -gt 0) {
        Write-Host "[CI-Stream] Monitoring output for ${LogDurationSeconds} seconds..."
        $proc = Start-Process -FilePath $Script:Adb -ArgumentList @("-s", $Script:TargetSerial, "logcat", "-v", "time", "-s", $filter) -RedirectStandardOutput $Script:LogcatFile -NoNewWindow -PassThru
        
        $elapsed = 0
        $lastLineCount = 0
        while ($elapsed -lt $LogDurationSeconds) {
            Start-Sleep -Seconds 2
            $elapsed += 2
            if (Test-Path $Script:LogcatFile) {
                $lines = Get-Content $Script:LogcatFile
                if ($lines.Count -gt $lastLineCount) {
                    $lines[$lastLineCount..($lines.Count - 1)] | ForEach-Object { Write-Host "[Device] $_" }
                    $lastLineCount = $lines.Count
                }
            }
        }
        if (-not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "[CI-Stream] Streaming in foreground until interrupted..."
        & $Script:Adb -s $Script:TargetSerial logcat -v time -s $filter | Tee-Object -FilePath $Script:LogcatFile
    }

    # Audit for crashes
    if (Test-Path $Script:LogcatFile) {
        $crashes = Select-String -Path $Script:LogcatFile -Pattern "FATAL EXCEPTION|SIGSEGV|SIGABRT|CRASH"
        if ($crashes) {
            Write-Warning "[CI-Stream] Crash detected in logcat output:"
            $crashes | ForEach-Object { Write-Host $_.Line }
        } else {
            Write-Host "[CI-Stream] No fatal exceptions detected during monitoring period."
        }
    }
}

function Complete-Pipeline {
    Write-Host "[CI-Done] Summary session log: $Script:CiLogFile"
    Write-Host "[CI-Done] Application logcat log: $Script:LogcatFile"
    Stop-Transcript | Out-Null
}
#endregion

#region Core
Write-Host "[CI-Core] Executing WebGPU Android toolchain..."
Initialize-Environment
Initialize-Directories
try {
    if ($EmulatorOnly) {
        Ensure-Emulator
        return
    }
    if (-not $DeployOnly) {
        Invoke-Build
        Invoke-Package
    }
    if (-not $BuildOnly) {
        Ensure-Emulator
        Invoke-Deploy
        Stream-Logs
    }
} finally {
    Complete-Pipeline
}
Write-Host "[CI-Core] Execution finished."
#endregion
