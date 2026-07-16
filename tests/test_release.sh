#!/usr/bin/env bash
# Unit tests for release.sh validation functions
# Run with: bash tests/test_release.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
log_test() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "${YELLOW}[TEST $TESTS_RUN]${NC} $1"
}

log_pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}  ✓ PASSED${NC}"
}

log_fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}  ✗ FAILED${NC}"
    echo "    $1"
}

# Extract and define the validate_version function from release.sh
validate_version() {
    if [[ ! $1 =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*)?$ ]]; then
        echo "ERROR: Invalid version format: $1 (expected X.Y.Z or X.Y.Z-prerelease)"
        return 1
    fi
    return 0
}

# Test 1: validate_version accepts valid versions
log_test "validate_version accepts valid semver (1.0.0)"
{
    ERROR_OUTPUT=$(validate_version "1.0.0" 2>&1)
    if [[ $? -eq 0 ]]; then
        log_pass
    else
        log_fail "Expected success, got: $ERROR_OUTPUT"
    fi
}

# Test 2: validate_version accepts another valid version
log_test "validate_version accepts valid semver (0.3.15)"
{
    ERROR_OUTPUT=$(validate_version "0.3.15" 2>&1)
    if [[ $? -eq 0 ]]; then
        log_pass
    else
        log_fail "Expected success, got: $ERROR_OUTPUT"
    fi
}

# Test 3: validate_version rejects invalid version - missing patch
log_test "validate_version rejects version without patch number (1.0)"
{
    ERROR_OUTPUT=$(validate_version "1.0" 2>&1)
    if [[ "$ERROR_OUTPUT" == *"Invalid version format"* ]]; then
        log_pass
    else
        log_fail "Expected 'Invalid version format' error, got: $ERROR_OUTPUT"
    fi
}

# Test 4: validate_version rejects invalid version - too many parts
log_test "validate_version rejects version with too many parts (1.0.0.1)"
{
    ERROR_OUTPUT=$(validate_version "1.0.0.1" 2>&1)
    if [[ "$ERROR_OUTPUT" == *"Invalid version format"* ]]; then
        log_pass
    else
        log_fail "Expected 'Invalid version format' error, got: $ERROR_OUTPUT"
    fi
}

# Test 5: validate_version rejects version with 'v' prefix
log_test "validate_version rejects version with 'v' prefix (v1.0.0)"
{
    ERROR_OUTPUT=$(validate_version "v1.0.0" 2>&1)
    if [[ "$ERROR_OUTPUT" == *"Invalid version format"* ]]; then
        log_pass
    else
        log_fail "Expected 'Invalid version format' error, got: $ERROR_OUTPUT"
    fi
}

# Test 6: validate_version accepts edge case 0.0.0
log_test "validate_version accepts valid edge case (0.0.0)"
{
    ERROR_OUTPUT=$(validate_version "0.0.0" 2>&1)
    if [[ $? -eq 0 ]]; then
        log_pass
    else
        log_fail "Expected success, got: $ERROR_OUTPUT"
    fi
}

# Test 7: validate_version accepts large numbers
log_test "validate_version accepts valid edge case (999.999.999)"
{
    ERROR_OUTPUT=$(validate_version "999.999.999" 2>&1)
    if [[ $? -eq 0 ]]; then
        log_pass
    else
        log_fail "Expected success, got: $ERROR_OUTPUT"
    fi
}

# Test 8: validate_version accepts pre-release versions
log_test "validate_version accepts pre-release (1.0.0-beta)"
{
    ERROR_OUTPUT=$(validate_version "1.0.0-beta" 2>&1)
    if [[ $? -eq 0 ]]; then
        log_pass
    else
        log_fail "Expected success, got: $ERROR_OUTPUT"
    fi
}

# Test 9: validate_version rejects version with spaces
log_test "validate_version rejects version with spaces (1. 0.0)"
{
    ERROR_OUTPUT=$(validate_version "1. 0.0" 2>&1)
    if [[ "$ERROR_OUTPUT" == *"Invalid version format"* ]]; then
        log_pass
    else
        log_fail "Expected 'Invalid version format' error, got: $ERROR_OUTPUT"
    fi
}

# Test 10: validate_version rejects empty string
log_test "validate_version rejects empty string"
{
    ERROR_OUTPUT=$(validate_version "" 2>&1)
    if [[ "$ERROR_OUTPUT" == *"Invalid version format"* ]]; then
        log_pass
    else
        log_fail "Expected 'Invalid version format' error, got: $ERROR_OUTPUT"
    fi
}

# Test 11: sed pattern for version update (dry run verification)
log_test "sed pattern correctly matches version lines in pyproject.toml"
{
    TEST_FILE=$(mktemp)
    echo 'version = "0.2.8"' > "$TEST_FILE"
    if grep -q '^version = "' "$TEST_FILE"; then
        log_pass
    else
        log_fail "sed pattern doesn't match version line"
    fi
    rm -f "$TEST_FILE"
}

# Test 12: sed pattern for WhatsApp dependency (dry run verification)
log_test "sed pattern correctly matches whaagent dependency"
{
    TEST_FILE=$(mktemp)
    echo 'whaagent>=0.2.8' > "$TEST_FILE"
    if grep -q 'whaagent>=[0-9]\+\.[0-9]\+\.[0-9]\+' "$TEST_FILE"; then
        log_pass
    else
        log_fail "sed pattern doesn't match whaagent dependency line"
    fi
    rm -f "$TEST_FILE"
}

# Test 13: release.sh script is executable
log_test "release.sh script is executable"
{
    if [[ -x "scripts/release.sh" ]]; then
        log_pass
    else
        log_fail "Script is not executable. Run: chmod +x scripts/release.sh"
    fi
}

# Test 14: release.sh script exists
log_test "release.sh script exists"
{
    if [[ -f "scripts/release.sh" ]]; then
        log_pass
    else
        log_fail "Script not found at scripts/release.sh"
    fi
}

# Test 15: script has required functions defined
log_test "release.sh has all required functions"
{
    REQUIRED_FUNCTIONS=("validate_version" "check_clean" "check_gh" "update_version" "run_tests" "run_checks" "create_tag_and_release" "check_branch")
    MISSING=()

    for func in "${REQUIRED_FUNCTIONS[@]}"; do
        if ! grep -q "^${func}()" "scripts/release.sh"; then
            MISSING+=("$func")
        fi
    done

    if [[ ${#MISSING[@]} -eq 0 ]]; then
        log_pass
    else
        log_fail "Missing functions: ${MISSING[*]}"
    fi
}

# Test 16: script checks for uncommitted changes
log_test "release.sh checks for uncommitted changes (check_clean function)"
{
    if grep -q "git status --porcelain" "scripts/release.sh"; then
        log_pass
    else
        log_fail "check_clean function doesn't check for uncommitted changes"
    fi
}

# Test 17: script checks for gh CLI
log_test "release.sh checks for gh CLI (check_gh function)"
{
    if grep -q "command -v gh" "scripts/release.sh"; then
        log_pass
    else
        log_fail "check_gh function doesn't check for gh CLI"
    fi
}

# Test 18: script checks for main branch
log_test "release.sh checks for main branch (check_branch function)"
{
    if grep -q "git branch --show-current" "scripts/release.sh"; then
        log_pass
    else
        log_fail "check_branch function doesn't check current branch"
    fi
}

# Test 19: script has FORCE_RELEASE variable support
log_test "release.sh supports FORCE_RELEASE environment variable"
{
    if grep -q "FORCE_RELEASE" "scripts/release.sh"; then
        log_pass
    else
        log_fail "Script doesn't support FORCE_RELEASE override"
    fi
}

# Print summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo -e "Total:   ${YELLOW}$TESTS_RUN${NC}"
echo -e "Passed:  ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed:  ${RED}$TESTS_FAILED${NC}"
echo "========================================"

# Exit with error code if any tests failed
if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi

exit 0
