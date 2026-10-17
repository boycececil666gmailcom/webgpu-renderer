#!/usr/bin/env bash
#region Imports
set -euo pipefail
#endregion

#region Types
TEST_DURATION="${TEST_DURATION:-25}"
HEADLESS="${HEADLESS:-false}"
RESTART_EMU=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --headless)       HEADLESS="true"; shift ;;
        --window|--gui)   HEADLESS="false"; shift ;;
        -r|--restart-emu) RESTART_EMU=true; shift ;;
        -l|--duration)    TEST_DURATION="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done
#endregion

#region Scaffolding
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log_step() {
    local label="$1"
    local message="$2"
    printf "\n\033[1;36m========================================================\033[0m\n"
    printf "\033[1;32m>>> [%s] %s\033[0m\n" "${label}" "${message}"
    printf "\033[1;36m========================================================\033[0m\n\n"
}
#endregion

#region Test
run_unit_tests() {
    log_step "Compile-Check" "Verifying engine compilation and test artifacts"
    (cd "${PROJECT_ROOT}" && cargo test --no-run --quiet)
}

run_android_pipeline() {
    local mode_desc="visible GUI"
    [ "${HEADLESS}" = "true" ] && mode_desc="headless"
    log_step "Android-CI" "Running build, deploy, and telemetry sampling (${TEST_DURATION}s, mode: ${mode_desc})"
    local flags=("-l" "${TEST_DURATION}")
    if [ "${HEADLESS}" = "true" ]; then
        flags+=("--headless")
    fi
    if [ "${RESTART_EMU}" = "true" ]; then
        flags+=("-r")
    fi
    bash "${PROJECT_ROOT}/android/ci.sh" "${flags[@]}"
}

audit_telemetry() {
    log_step "Telemetry-Audit" "Checking logcat for fatal signals and runtime errors"
    local logcat_file="${PROJECT_ROOT}/android/logs/logcat_latest.log"
    if [ ! -f "${logcat_file}" ]; then
        printf "\033[1;31m[Audit-Failed] Missing logcat file at %s\033[0m\n" "${logcat_file}" >&2
        return 1
    fi
    if grep -E "FATAL EXCEPTION|SIGSEGV|SIGABRT|panic|CRASH" "${logcat_file}" >/dev/null 2>&1; then
        printf "\033[1;31m[Audit-Failed] Fatal crash detected in device logs.\033[0m\n" >&2
        grep -E "FATAL EXCEPTION|SIGSEGV|SIGABRT|panic|CRASH" "${logcat_file}" >&2
        return 1
    fi
    printf "\033[1;32m[Audit-Passed] Application executed with zero fatal signals.\033[0m\n"
}
#endregion

#region Core
orchestrate_ci() {
    run_unit_tests
    run_android_pipeline
    audit_telemetry
}
#endregion

#region Main
main() {
    orchestrate_ci
    printf "\n\033[1;32m[CI-E2E] End-to-end testing pipeline completed successfully.\033[0m\n"
}

main "$@"
#endregion
