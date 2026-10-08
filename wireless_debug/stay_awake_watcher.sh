#!/system/bin/sh
# region Watcher
# Keep-awake watcher for Android Wireless Debugging
# Automatically restores normal screen sleep timeout when Wireless Debugging is disabled on the device.

BACKUP_FILE="/data/local/tmp/orig_screen_timeout"
if [ -f "$BACKUP_FILE" ]; then
    RESTORE_TIMEOUT=$(cat "$BACKUP_FILE" 2>/dev/null)
else
    RESTORE_TIMEOUT="300000"
fi

case "$RESTORE_TIMEOUT" in
    ''|*[!0-9]*) RESTORE_TIMEOUT="300000" ;;
esac

while true; do
    sleep 3
    WIFI_ENABLED=$(settings get global adb_wifi_enabled 2>/dev/null)
    if [ "$WIFI_ENABLED" != "1" ]; then
        settings put system screen_off_timeout "$RESTORE_TIMEOUT"
        svc power stayon false
        rm -f "$BACKUP_FILE"
        exit 0
    fi
done
# endregion
