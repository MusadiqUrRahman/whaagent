#!/usr/bin/env bash
# Cross-compile Go gateway and upload binaries to a GitHub Release.
#
# Usage:
#   ./scripts/build-gateway.sh v1.0.0-beta
#
# Prerequisites:
#   - Go 1.25+ installed
#   - gh CLI authenticated
#   - Tag must already exist as a GitHub Release
#
# Produces:
#   whaagent-gateway-linux-amd64
#   whaagent-gateway-linux-arm64
#   whaagent-gateway-darwin-amd64
#   whaagent-gateway-darwin-arm64

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

TAG="${1:-}"
if [[ -z "$TAG" ]]; then
    log_error "Usage: $0 TAG  (e.g., v1.0.0-beta)"
fi

VERSION="${TAG#v}"
GATEWAY_DIR="$(git rev-parse --show-toplevel)/gateway"
DIST_DIR="$(git rev-parse --show-toplevel)/dist/gateway"

# Verify gateway source exists
if [[ ! -f "$GATEWAY_DIR/main.go" ]]; then
    log_error "gateway/main.go not found. Run from repo root."
fi

# Verify Go is installed and meets minimum version
if ! command -v go &>/dev/null; then
    log_error "Go is required. Install: https://go.dev/dl/"
fi
GO_VERSION=$(go version | grep -oP 'go\K[0-9]+\.[0-9]+' | head -1)
REQUIRED_VERSION="1.25"
if [[ "$(printf '%s\n' "$REQUIRED_VERSION" "$GO_VERSION" | sort -V | head -1)" != "$REQUIRED_VERSION" ]]; then
    log_error "Go >= $REQUIRED_VERSION required, got $GO_VERSION. Update: https://go.dev/dl/"
fi

# Verify release exists on GitHub
if ! gh release view "$TAG" &>/dev/null; then
    log_error "GitHub release '$TAG' not found. Create it first with release.sh"
fi

# Build targets: OS/ARCH pairs
TARGETS=(
    "linux/amd64"
    "linux/arm64"
    "darwin/amd64"
    "darwin/arm64"
)

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

BUILT_FILES=()

for TARGET in "${TARGETS[@]}"; do
    IFS='/' read -r GOOS GOARCH <<< "$TARGET"
    BINARY_NAME="whaagent-gateway-${GOOS}-${GOARCH}"

    # Add .exe for Windows (if added later)
    if [[ "$GOOS" == "windows" ]]; then
        BINARY_NAME="${BINARY_NAME}.exe"
    fi

    log_info "Building $BINARY_NAME..."

    CGO_ENABLED=0 GOOS="$GOOS" GOARCH="$GOARCH" \
        go build -trimpath -ldflags="-s -w -X main.version=$VERSION" \
        -o "$DIST_DIR/$BINARY_NAME" \
        "$GATEWAY_DIR"

    BUILT_FILES+=("$BINARY_NAME")
    log_info "  OK: $(du -h "$DIST_DIR/$BINARY_NAME" | cut -f1)"
done

# Upload all binaries to the GitHub Release
log_info "Uploading ${#BUILT_FILES[@]} binaries to release $TAG..."

UPLOAD_ARGS=()
for FILE in "${BUILT_FILES[@]}"; do
    UPLOAD_ARGS+=("$DIST_DIR/$FILE")
done

gh release upload "$TAG" "${UPLOAD_ARGS[@]}" --clobber

log_info "Done! Binaries uploaded to:"
echo "  https://github.com/jeancsil/whaagent/releases/tag/$TAG"
echo ""
echo "Users can download with:"
echo "  curl -L -o whaagent-gateway https://github.com/jeancsil/whaagent/releases/download/$TAG/whaagent-gateway-<os>-<arch>"
echo "  chmod +x whaagent-gateway"
