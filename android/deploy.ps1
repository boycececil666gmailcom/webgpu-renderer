#region Config
param(
    [string]$DeviceIp = "10.36.154.26",
    [switch]$SkipInstall
)

$AndroidDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $AndroidDir "..")).Path
$Adb = if (Test-Path "C:\Users\boyce\platform-tools\adb.exe") { "C:\Users\boyce\platform-tools\adb.exe" } else { "adb" }
$Package = "org.antigravity.webgpurenderer"
$Activity = "android.app.NativeActivity"
#endregion

#region Connect
$devices = & $Adb devices -l
$active = @($devices | Where-Object { $_ -match "^(\S+)\s+device\b" } | ForEach-Object { ($_.Trim() -split "\s+")[0] })

if ($active.Count -eq 0) {
    Write-Host "[Deploy-Connect] Discovering device on $DeviceIp..."
    $port = ""
    $mdns = & $Adb mdns services 2>&1
    foreach ($line in $mdns) {
        if ($line -match "_adb-tls-connect\._tcp\s+$([regex]::Escape($DeviceIp)):(\d+)") {
            $port = $Matches[1]
            break
        }
    }
    if ($port) {
        & $Adb connect "$DeviceIp`:$port" | Out-Null
    } else {
        & $Adb connect "$DeviceIp`:5555" | Out-Null
    }
    $devices = & $Adb devices -l
    $active = @($devices | Where-Object { $_ -match "^(\S+)\s+device\b" } | ForEach-Object { ($_.Trim() -split "\s+")[0] })
}

if ($active.Count -eq 0) {
    Write-Host "[Deploy-Connect] Error: No active ADB device found."
    Write-Host "[Deploy-Connect] Tip: Verify Wireless Debugging is enabled on phone, or run: $Adb connect $DeviceIp`:<port>"
    exit 1
}

$Serial = $active[0]
Write-Host "[Deploy-Connect] Target device: $Serial"
#endregion

#region Install
if (-not $SkipInstall) {
    $apk = (Get-ChildItem -Path (Join-Path $ProjectRoot "bin") -Filter "*.apk" -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    if (-not $apk) {
        Write-Host "[Deploy-Install] Error: No APK found in bin/. Run .\android\build.ps1 first."
        exit 1
    }
    Write-Host "[Deploy-Install] Installing $(Split-Path $apk -Leaf)..."
    $res = & $Adb -s $Serial install -r $apk 2>&1
    $res | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0 -or ($res -match "INSTALL_FAILED_UPDATE_INCOMPATIBLE")) {
        Write-Host "[Deploy-Install] Reinstalling clean build..."
        & $Adb -s $Serial uninstall $Package | Out-Null
        & $Adb -s $Serial install $apk
    }
}
#endregion

#region Launch
Write-Host "[Deploy-Launch] Starting $Package..."
& $Adb -s $Serial logcat -c
& $Adb -s $Serial shell am start -n "$Package/$Activity" | Out-Null

Write-Host "[Deploy-Launch] Streaming logs (Ctrl+C to stop)..."
& $Adb -s $Serial logcat -v time -s WebGpuEngine:* RustStdoutStderr:* AndroidRuntime:* CRASH:* DEBUG:* *:F
#endregion
