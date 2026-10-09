#region Config
param(
    [string]$DeviceIp = "10.36.154.26",
    [string]$PairPort,
    [string]$PairCode,
    [string]$ConnectPort,
    [switch]$SkipInstall,
    [switch]$Disconnect,
    [switch]$KeepAwakeOnly,
    [switch]$PersistentAwake
)

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "debug_$Timestamp.log"
$LatestLogFile = Join-Path $LogDir "latest.log"
$BackupTimeoutFile = Join-Path $LogDir ".screen_timeout_backup"
$WatcherScript = Join-Path $PSScriptRoot "stay_awake_watcher.sh"

$AdbPath = "C:\Users\boyce\platform-tools\adb.exe"
if (-not (Test-Path $AdbPath)) { $AdbPath = "adb" }
$PackageName = "org.antigravity.webgpurenderer"
$ActivityName = "org.kivy.android.PythonActivity"
$Script:TargetSerial = ""
#endregion

#region Logging
$utf8Encoding = New-Object System.Text.UTF8Encoding($false)

function Write-StepLog {
    param([string]$Func, [string]$Msg)
    $formatted = "[Deploy-$Func] $Msg"
    Write-Host $formatted
    [System.IO.File]::AppendAllText($LogFile, "$formatted`r`n", $utf8Encoding)
}

function Write-LogLine {
    param([string]$Text)
    Write-Host $Text
    [System.IO.File]::AppendAllText($LogFile, "$Text`r`n", $utf8Encoding)
}

function Tee-Utf8 {
    param([string]$Path)
    process {
        Write-Host $_
        [System.IO.File]::AppendAllText($Path, "$_`r`n", [System.Text.UTF8Encoding]::new($false))
    }
}
#endregion

#region Helper
function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)]$AdbArgs)
    if ($Script:TargetSerial) {
        & $AdbPath -s $Script:TargetSerial @AdbArgs
    } else {
        & $AdbPath @AdbArgs
    }
}

function Get-ActiveDevices {
    $lines = & $AdbPath devices -l
    $list = @()
    foreach ($line in $lines) {
        $trimmed = ($line | Out-String).Trim()
        if ($trimmed -match '^(\S+)\s+device\b') {
            $list += $Matches[1]
        }
    }
    return $list
}
#endregion

#region Power
function Enable-KeepAwake {
    param([string]$AdbPath)

    # 1. Capture current screen timeout
    $rawTimeout = Invoke-Adb shell settings get system screen_off_timeout 2>&1
    $current = ($rawTimeout | Out-String).Trim()
    if ($current -and $current -ne "2147483647" -and $current -match '^\d+$') {
        Set-Content -Path $BackupTimeoutFile -Value $current -Encoding utf8
        Invoke-Adb shell "echo '$current' > /data/local/tmp/orig_screen_timeout"
        Write-StepLog "Power" "Backed up original screen timeout: $($current)ms."
    } elseif (-not (Test-Path $BackupTimeoutFile)) {
        Set-Content -Path $BackupTimeoutFile -Value "300000" -Encoding utf8
        Invoke-Adb shell "echo '300000' > /data/local/tmp/orig_screen_timeout"
    }

    # 2. Configure screen to never sleep
    Invoke-Adb shell settings put system screen_off_timeout 2147483647
    Invoke-Adb shell svc power stayon true
    Write-StepLog "Power" "Screen set to never sleep (timeout: 2147483647ms, stayon: true)."

    # 3. Deploy and launch on-device watcher daemon
    if (Test-Path $WatcherScript) {
        Invoke-Adb push $WatcherScript /data/local/tmp/stay_awake_watcher.sh | Out-Null
        Invoke-Adb shell "chmod 755 /data/local/tmp/stay_awake_watcher.sh"
        Invoke-Adb shell "pkill -f '[s]tay_awake_watcher' 2>/dev/null"
        Invoke-Adb shell "nohup sh /data/local/tmp/stay_awake_watcher.sh > /dev/null 2>&1 &"
        Write-StepLog "Power" "On-device watcher daemon started. Normal sleep will auto-restore when Wireless Debugging is disabled."
    }
}

function Disable-KeepAwake {
    param([string]$AdbPath)

    $restored = "300000"
    if (Test-Path $BackupTimeoutFile) {
        $saved = (Get-Content -Path $BackupTimeoutFile -Raw -ErrorAction SilentlyContinue).Trim()
        if ($saved -and $saved -ne "2147483647") {
            $restored = $saved
        }
    }

    # Terminate on-device watcher daemon
    Invoke-Adb shell "pkill -f '[s]tay_awake_watcher' 2>/dev/null"
    Invoke-Adb shell "rm -f /data/local/tmp/stay_awake_watcher.sh /data/local/tmp/orig_screen_timeout 2>/dev/null"
    Invoke-Adb shell settings put system screen_off_timeout $restored
    Invoke-Adb shell svc power stayon false
    Write-StepLog "Power" "Restored screen sleep timeout ($($restored)ms). Keep-awake disabled."
}
#endregion

#region Server
# Ensure persistent background ADB server is running
$adbProc = Get-Process -Name adb -ErrorAction SilentlyContinue
if (-not $adbProc) {
    Write-StepLog "Server" "Starting persistent background ADB server..."
    Start-Process -FilePath $AdbPath -ArgumentList "-a -P 5037 server nodaemon" -WindowStyle Hidden
    Start-Sleep -Seconds 1
}
#endregion

#region Wireless
# 1. Handle explicit disconnect request
if ($Disconnect) {
    Write-StepLog "Power" "Restoring sleep settings and terminating wireless ADB session..."
    Disable-KeepAwake -AdbPath $AdbPath
    & $AdbPath disconnect | Tee-Utf8 -Path $LogFile
    Write-StepLog "Wireless" "Wireless ADB session disconnected."
    exit 0
}

# 2. Pair if pairing parameters supplied
if ($PairPort -and $PairCode) {
    Write-StepLog "Pair" "Pairing with $DeviceIp`:$PairPort using code $PairCode..."
    $pairOut = & $AdbPath pair "$DeviceIp`:$PairPort" $PairCode 2>&1
    Write-LogLine $pairOut
}

# 3. Check for existing active device session (IP or mDNS TLS)
$activeSerials = @(Get-ActiveDevices)
$deviceAlreadyConnected = $false
foreach ($serial in $activeSerials) {
    if ($serial -match "^$DeviceIp`:\d+" -or $serial -match "^adb-.*_adb-tls-connect\._tcp") {
        $deviceAlreadyConnected = $true
        break
    }
}

if (-not $deviceAlreadyConnected -and -not $ConnectPort) {
    Write-StepLog "Connect" "Scanning for wireless debugging mDNS service for $DeviceIp..."
    $mdnsLines = & $AdbPath mdns services 2>&1
    foreach ($line in $mdnsLines) {
        if ($line -match "_adb-tls-connect\._tcp\s+($DeviceIp`:(\d+))") {
            $ConnectPort = $Matches[2]
            Write-StepLog "Connect" "Auto-discovered active wireless port via mDNS: $ConnectPort"
            break
        }
    }
}

# 4. Connect if connect port determined and not yet connected
if ($ConnectPort -and -not $deviceAlreadyConnected) {
    Write-StepLog "Connect" "Connecting to $DeviceIp`:$ConnectPort..."
    $connOut = & $AdbPath connect "$DeviceIp`:$ConnectPort" 2>&1
    Write-LogLine $connOut
    $activeSerials = @(Get-ActiveDevices)
}

# 5. Verify active connected device and select target serial
$activeSerials = @(Get-ActiveDevices)

if ($activeSerials.Count -eq 0) {
    Write-StepLog "Device" "No active wireless device detected."
    Write-StepLog "Device" "To pair:       .\wireless_debug\deploy.ps1 -PairPort <Port> -PairCode <Code>"
    Write-StepLog "Device" "To connect:    .\wireless_debug\deploy.ps1 -ConnectPort <Port>"
    Write-StepLog "Device" "To disconnect: .\wireless_debug\deploy.ps1 -Disconnect"
    & $AdbPath devices -l | Tee-Utf8 -Path $LogFile
    exit 1
}

# If multiple endpoints exist, prioritize IP or mDNS, and disconnect any conflicting duplicate
if ($activeSerials.Count -gt 1) {
    $ipSerial = $activeSerials | Where-Object { $_ -match "^$DeviceIp`:\d+" } | Select-Object -First 1
    $mdnsSerial = $activeSerials | Where-Object { $_ -match "^adb-.*_adb-tls-connect\._tcp" } | Select-Object -First 1
    if ($ipSerial -and $mdnsSerial) {
        Write-StepLog "Device" "Deduplicating connection: dropping redundant endpoint $ipSerial in favor of mDNS session..."
        & $AdbPath disconnect $ipSerial 2>&1 | Out-Null
        $activeSerials = @(Get-ActiveDevices)
    }
}

$Script:TargetSerial = $activeSerials[0]
Write-StepLog "Device" "Target serial selected: $Script:TargetSerial"
(& $AdbPath devices -l) | Where-Object { $_ -match "\bdevice\b" } | ForEach-Object { Write-StepLog "Device" "  $_" }

# 6. Enable keep-awake on active phone
Enable-KeepAwake -AdbPath $AdbPath

if ($KeepAwakeOnly) {
    Write-StepLog "Power" "Keep-awake setup completed. Exiting as requested by -KeepAwakeOnly."
    exit 0
}
#endregion

#region Deployment
$BinDir = Join-Path $RootDir "bin"
$ApkPath = (Get-ChildItem -Path $BinDir -Filter "*.apk" -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
if (-not $ApkPath) {
    Write-StepLog "Build" "Error: No APK found in $BinDir"
    exit 1
}

if (-not $SkipInstall) {
    Write-StepLog "Install" "Installing $ApkPath over Wi-Fi..."
    $installOut = Invoke-Adb install -r $ApkPath 2>&1
    $installOut | ForEach-Object { Write-LogLine $_ }
    if ($LASTEXITCODE -ne 0 -or ($installOut -match "INSTALL_FAILED_UPDATE_INCOMPATIBLE")) {
        Write-StepLog "Install" "Signature mismatch detected. Performing clean reinstall..."
        Invoke-Adb uninstall $PackageName | Tee-Utf8 -Path $LogFile
        Write-StepLog "Install" "Reinstalling fresh build..."
        Invoke-Adb install $ApkPath | Tee-Utf8 -Path $LogFile
        if ($LASTEXITCODE -ne 0) {
            Write-StepLog "Install" "Installation failed. Check phone screen for authorization prompt."
            exit 1
        }
    }
    Write-StepLog "Install" "Installation complete."
}
#endregion

#region Launch
Write-StepLog "Launch" "Clearing logcat buffer..."
Invoke-Adb logcat -c

Write-StepLog "Launch" "Starting $PackageName/$ActivityName..."
Invoke-Adb shell am start -n "$PackageName/$ActivityName" | Tee-Utf8 -Path $LogFile

Write-StepLog "Stream" "Capturing live execution and crash logs to $LogFile..."
Write-StepLog "Stream" "Monitored tags: python, pythonutil, SDL, SDLActivity, libc, AndroidRuntime, DEBUG"
Write-StepLog "Stream" "Press Ctrl+C to terminate log capture."

try {
    # Stream live logcat and mirror to disk in pure UTF-8
    Invoke-Adb logcat -v time -s python:* pythonutil:* SDL:* SDLActivity:* System.err:* AndroidRuntime:* CRASH:* DEBUG:* libc:* *:F | Tee-Utf8 -Path $LogFile
}
finally {
    # 1. Query Android OS Process Exit Info on teardown
    $exitHeader = "`n--- Android OS Process Exit Info ---"
    Write-LogLine $exitHeader
    $exitInfo = Invoke-Adb shell dumpsys activity exit-info $PackageName | Select-Object -First 18
    $exitInfo | ForEach-Object {
        Write-LogLine "  $_"
    }

    # 2. Revert screen sleep timeout unless -PersistentAwake requested
    if (-not $PersistentAwake) {
        Disable-KeepAwake -AdbPath $AdbPath
    } else {
        Write-StepLog "Power" "Persistent keep-awake active. On-device watcher will auto-restore sleep if wireless debugging is turned off."
    }

    Copy-Item -Path $LogFile -Destination $LatestLogFile -Force
    Write-StepLog "Log" "Session log saved: $LogFile"
    Write-StepLog "Log" "Latest link updated: $LatestLogFile"
}
#endregion
