# Wireless Android Debugging & Deployment

Dedicated workspace for wireless ADB pairing, APK deployment, execution, keep-awake power management, and crash diagnostic logging.

## Directory Structure

```text
wireless_debug/
├── deploy.ps1              # Unified deployment, launch, power management, and log collection
├── stay_awake_watcher.sh   # On-device background watcher for auto-reverting sleep
├── logs/                   # Pure UTF-8 session logs (timestamped + latest.log)
│   ├── .gitkeep
│   ├── .screen_timeout_backup
│   ├── debug_*.log
│   └── latest.log
└── README.md
```

## Screen Keep-Awake Behavior

- **Automatic Keep-Awake**: Whenever the script connects to your phone via ADB, it backs up your phone's normal screen timeout and automatically sets `screen_off_timeout` to maximum (~24.8 days) and `svc power stayon true` so the phone **never sleeps** during debugging.
- **On-Device Auto-Restore**: If you turn off Wireless Debugging directly in Android Settings on your phone, the on-device watcher daemon (`stay_awake_watcher.sh`) automatically detects that `adb_wifi_enabled` is no longer active and instantly reverts the screen timeout back to your original setting (e.g. 5 minutes).
- **Graceful Teardown**: When you stop the script via Ctrl+C or upon normal completion, it automatically restores normal sleep unless `-PersistentAwake` is specified.
- **Explicit Disconnect**: Run `deploy.ps1 -Disconnect` to kill the watcher, restore normal sleep timeout, and disconnect wireless ADB.

## Quick Start

### 1. Auto-Connect & Set Never-Sleep (No Deploy)
Auto-detects the phone's port via mDNS and configures keep-awake:
```powershell
powershell -ExecutionPolicy Bypass -File wireless_debug\deploy.ps1 -KeepAwakeOnly
```

### 2. Full Build Deployment
Auto-discovers port, pushes newest APK from `bin/`, sets never-sleep, launches app, and streams live crash logs:
```powershell
powershell -ExecutionPolicy Bypass -File wireless_debug\deploy.ps1
```

### 3. Launch & Stream Logs (Skip Re-installation)
```powershell
powershell -ExecutionPolicy Bypass -File wireless_debug\deploy.ps1 -SkipInstall
```

### 4. Disconnect & Restore Normal Sleep
```powershell
powershell -ExecutionPolicy Bypass -File wireless_debug\deploy.ps1 -Disconnect
```

### 5. Pair New Device / Port
```powershell
powershell -ExecutionPolicy Bypass -File wireless_debug\deploy.ps1 -PairPort <Port> -PairCode <Code>
```

## UTF-8 Log Files
All console output, logcat streams, and Android OS `dumpsys activity exit-info` reports are strictly encoded in standard UTF-8 text (no UTF-16LE null-byte corruption):
- `wireless_debug/logs/debug_<YYYYMMDD_HHMMSS>.log` (timestamped persistent record)
- `wireless_debug/logs/latest.log` (pointer to the most recent run)
