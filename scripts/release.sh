#!/usr/bin/env bash
# Release script for whaagent
#
# Usage:
#   ./scripts/release.sh 1.0.0-alpha
#   ./scripts/release.sh 1.0.0-beta.1
#   ./scripts/release.sh 1.0.0-rc.2
#   ./scripts/release.sh 1.0.0
#
# Prerequisites:
#   - gh CLI installed and authenticated
#   - No uncommitted changes
#   - All tests passing
#
# Pre-release versions (containing -alpha, -beta, -rc) are published to
# TestPyPI. Stable versions are published to PyPI.
#
# Environment Variables:
#   - FORCE_RELEASE=1: Bypass branch check (use with caution)
#   - SKIP_TESTS=1:    Skip test execution

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Validation ──────────────────────────────────────────────────────

validate_version() {
    local version="$1"
    # Full semver: X.Y.Z with optional pre-release (-alpha, -beta.1, -rc.2, etc.)
    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*)?$ ]]; then
        log_error "Invalid version: '$version' (expected X.Y.Z or X.Y.Z-prerelease)"
    fi
}

is_prerelease() {
    [[ "$1" == *"-"* ]]
}

SKIP_GATEWAY="${SKIP_GATEWAY:-}"

check_branch() {
    local current_branch
    current_branch=$(git branch --show-current)
    if [[ "$current_branch" != "main" ]]; then
        if [[ "${FORCE_RELEASE:-}" != "1" ]]; then
            echo ""
            log_error "Releases must be from 'main' (currently: '$current_branch').
  Use FORCE_RELEASE=1 to bypass, or:
    git checkout main && git pull origin main"
        else
            log_warn "Bypassing branch check on '$current_branch'"
        fi
    fi
}

check_clean() {
    if [[ -n $(git status --porcelain) ]]; then
        log_error "Uncommitted changes. Commit or stash first."
    fi
}

check_gh() {
    if ! command -v gh &>/dev/null; then
        log_error "GitHub CLI (gh) is required. Install: https://cli.github.com"
    fi
}

# ── Actions ─────────────────────────────────────────────────────────

update_version() {
    local version="$1"
    sed -i.bak "s/^version = \".*\"/version = \"$version\"/" pyproject.toml
    rm -f pyproject.toml.bak
    log_info "Updated pyproject.toml to $version"
}

run_checks() {
    log_info "Running make check..."
    make check
}

run_tests() {
    if [[ "${SKIP_TESTS:-}" == "1" ]]; then
        log_warn "Skipping tests (SKIP_TESTS=1)"
        return
    fi
    log_info "Running make test..."
    make test
}

build_gateway() {
    if [[ "${SKIP_GATEWAY:-}" == "1" ]]; then
        log_warn "Skipping gateway build (SKIP_GATEWAY=1)"
        return
    fi
    if ! command -v go &>/dev/null; then
        log_warn "Go not installed, skipping gateway build"
        return
    fi
    log_info "Building gateway binaries..."
    bash "$(git rev-parse --show-toplevel)/scripts/build-gateway.sh" "v$version"
}

create_tag_and_release() {
    local version="$1"
    local tag="v$version"
    local prerelease=""

    if is_prerelease "$version"; then
        prerelease="--prerelease"
        log_info "Detected pre-release: $version"
    fi

    if git tag -l "$tag" | grep -q .; then
        log_error "Tag $tag already exists. Delete it first: git tag -d $tag && git push origin :refs/tags/$tag"
    fi

    log_info "Creating tag $tag..."
    git tag -a "$tag" -m "Release $tag"

    log_info "Pushing to origin..."
    git push origin HEAD --tags

    log_info "Creating GitHub release $tag..."
    local notes="## whaagent $tag

Released $(date +%Y-%m-%d)."

    gh release create "$tag" --title "$tag" --notes "$notes" $prerelease

    # Build and upload gateway binaries
    build_gateway

    if is_prerelease "$version"; then
        log_info "Pre-release published. GitHub Actions will publish to TestPyPI."
    else
        log_info "Stable release published. GitHub Actions will publish to PyPI."
    fi
}

# ── Main ────────────────────────────────────────────────────────────

main() {
    local version="${1:-}"

    if [[ -z "$version" ]]; then
        log_error "Usage: $0 VERSION
  Examples:
    $0 1.0.0-alpha
    $0 1.0.0-beta.1
    $0 1.0.0-rc.2
    $0 1.0.0
  Environment:
    SKIP_GATEWAY=1     Skip gateway binary build
    SKIP_TESTS=1       Skip test execution
    FORCE_RELEASE=1    Bypass branch check"
    fi

    validate_version "$version"
    check_gh
    check_clean
    check_branch

    update_version "$version"
    run_checks
    run_tests

    if git diff --quiet pyproject.toml; then
        log_warn "Version already set to $version in pyproject.toml"
    else
        git add pyproject.toml
        git commit -m "release: whaagent $version"
    fi

    create_tag_and_release "$version"

    echo ""
    log_info "Done! whaagent $version released."
    echo "  Tag: v$version"
    if is_prerelease "$version"; then
        echo "  PyPI: https://test.pypi.org/p/whaagent (pre-release)"
    else
        echo "  PyPI: https://pypi.org/p/whaagent"
    fi
    echo "  GitHub: https://github.com/jeancsil/whaagent/releases/tag/v$version"
}

main "$@"
