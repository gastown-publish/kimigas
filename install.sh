#!/bin/bash
# kimigas universal installer
# Usage: curl -fsSL https://raw.githubusercontent.com/gastown-publish/kimigas/main/install.sh | bash
set -euo pipefail

REPO="gastown-publish/kimigas"
BINARY_NAME="kimigas"
INSTALL_DIR="${KIMIGAS_INSTALL_DIR:-$HOME/.local/bin}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}==>${NC} $*"; }
warn() { echo -e "${YELLOW}==>${NC} $*"; }
error() { echo -e "${RED}Error:${NC} $*" >&2; exit 1; }

# Detect platform
detect_platform() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"

  case "$os" in
    linux)  OS="linux" ;;
    darwin) OS="darwin" ;;
    *)      error "Unsupported OS: $os" ;;
  esac

  case "$arch" in
    x86_64|amd64)  ARCH="x86_64"; TARGET="x86_64-unknown-linux-gnu" ;;
    aarch64|arm64) ARCH="aarch64"; TARGET="aarch64-unknown-linux-gnu" ;;
    *)             error "Unsupported architecture: $arch" ;;
  esac

  if [[ "$OS" == "darwin" ]]; then
    TARGET="aarch64-apple-darwin"
  fi
}

# Get latest version from GitHub
get_latest_version() {
  if command -v gh &>/dev/null; then
    VERSION=$(gh api "repos/${REPO}/releases/latest" --jq '.tag_name' 2>/dev/null | tr -d 'v')
  elif command -v curl &>/dev/null; then
    VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | grep -o '"tag_name": *"[^"]*"' | head -1 | grep -o 'v[0-9.]*' | tr -d 'v')
  else
    error "Need curl or gh CLI to detect latest version"
  fi

  if [[ -z "${VERSION:-}" ]]; then
    error "Could not determine latest version. Check https://github.com/${REPO}/releases"
  fi
}

install_binary() {
  local url="https://github.com/${REPO}/releases/download/v${VERSION}/kimigas-${VERSION}-${TARGET}.tar.gz"
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  info "Downloading kimigas v${VERSION} for ${TARGET}..."
  curl -fsSL "$url" -o "${tmp_dir}/kimigas.tar.gz" || error "Download failed. Check if release exists: $url"

  info "Installing to ${INSTALL_DIR}..."
  mkdir -p "$INSTALL_DIR"
  tar -xzf "${tmp_dir}/kimigas.tar.gz" -C "${tmp_dir}/"
  mv "${tmp_dir}/kimi" "${INSTALL_DIR}/${BINARY_NAME}"
  chmod +x "${INSTALL_DIR}/${BINARY_NAME}"

  # Create kimi symlink for upstream compatibility
  ln -sf "${INSTALL_DIR}/${BINARY_NAME}" "${INSTALL_DIR}/kimi"

  rm -rf "$tmp_dir"
}

check_path() {
  if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
    warn "${INSTALL_DIR} is not in your PATH"
    echo ""
    echo "Add to your shell profile:"
    echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
    echo ""
  fi
}

main() {
  info "kimigas installer"
  detect_platform
  get_latest_version
  install_binary
  check_path
  info "kimigas v${VERSION} installed successfully!"
  echo ""
  echo "  kimigas --version    # Verify installation"
  echo "  kimigas --help       # Get started"
  echo ""
}

main
