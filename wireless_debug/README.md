# Wireless Android Debugging & Deployment

Dedicated workspace for wireless ADB pairing, APK deployment, execution, and crash diagnostic logging.

## Directory Structure

```text
wireless_debug/
├── deploy.ps1              # Unified wireless connection, deployment, launch, and log collection
├── logs/                   # Pure UTF-8 session logs
│   └── .gitkeep
└── README.md
```

## Quick Start

### 1. Full Build Deployment
Auto-discovers target phone IP port, pushes newest APK from `bin/`, launches app, and streams live crash/Rust logs:
```powershell
powershell -ExecutionPolicy Bypass -File wireless_debug\deploy.ps1
```

### 2. Launch & Stream Logs (Skip Re-installation)
```powershell
powershell -ExecutionPolicy Bypass -File wireless_debug\deploy.ps1 -SkipInstall
```

### 3. Target Specific Device IP
```powershell
powershell -ExecutionPolicy Bypass -File wireless_debug\deploy.ps1 -DeviceIp "10.36.154.26"
```
