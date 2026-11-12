#!/usr/bin/env bash
#
# dotfiles installer - Bootstrap a new macOS machine
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ashtonian/dotfiles/master/install.sh | bash -s -- --profiles base,dev,desktop
#
# Or clone first:
#   git clone https://github.com/ashtonian/dotfiles.git ~/.dotfiles
#   ~/.dotfiles/install.sh --profiles base,dev,desktop
#
# Profiles are the files in profiles/, applied in the order given. Without
# --profiles (or DOTFILES_PROFILES), an existing machine manifest is kept, and
# otherwise the installer asks.
#

set -euo pipefail

#=============================================================================
# CONFIGURATION
#=============================================================================
DOTFILES_DIR="${HOME}/.dotfiles"
DOTFILES_REPO="https://github.com/ashtonian/dotfiles.git"
SYNC_DIR="${HOME}/.sync"
MACHINE_FILE="$HOME/.config/dotfiles/machine.toml"
DOTFILES_BIN="${DOTFILES_BIN:-$HOME/.local/bin/dotfiles}"
PROFILES="${DOTFILES_PROFILES:-}"

#=============================================================================
# COLORS & OUTPUT
#=============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

#=============================================================================
# SUDO SETUP
#=============================================================================
setup_sudo() {
    info "Checking sudo access..."

    # Check if already passwordless
    if sudo -n true 2>/dev/null; then
        success "Sudo access OK"
        return
    fi

    # Request sudo
    sudo -v

    # Keep sudo alive
    while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &
    SUDO_PID=$!
    trap 'kill $SUDO_PID 2>/dev/null' EXIT

    echo ""
    read -r -p "Enable passwordless sudo? [y/N] " response </dev/tty || response=""
    if [[ "$response" =~ ^[Yy]$ ]]; then
        if [[ ! "$LOGNAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
            error "Invalid username: $LOGNAME"
            exit 1
        fi
        info "Enabling passwordless sudo..."
        if ! grep -q "#includedir /private/etc/sudoers.d" /etc/sudoers 2>/dev/null; then
            echo '#includedir /private/etc/sudoers.d' | sudo tee -a /etc/sudoers > /dev/null
        fi
        echo -e "Defaults:$LOGNAME    !requiretty\n$LOGNAME ALL=(ALL) NOPASSWD: ALL" | sudo tee "/etc/sudoers.d/$LOGNAME" > /dev/null
        sudo chmod 0440 "/etc/sudoers.d/$LOGNAME"
        success "Passwordless sudo enabled"
    fi
}

#=============================================================================
# XCODE COMMAND LINE TOOLS
#=============================================================================
install_xcode_cli() {
    if xcode-select --print-path &>/dev/null; then
        success "Xcode CLI tools already installed"
        return
    fi

    info "Installing Xcode Command Line Tools..."
    xcode-select --install &>/dev/null

    # Wait for installation
    until xcode-select --print-path &>/dev/null; do
        sleep 5
    done

    sudo xcodebuild -license accept 2>/dev/null || true
    success "Xcode CLI tools installed"
}

#=============================================================================
# HOMEBREW
#=============================================================================
install_homebrew() {
    local brew_prefix; [[ "$(uname -m)" == "arm64" ]] && brew_prefix="/opt/homebrew" || brew_prefix="/usr/local"
    export PATH="$brew_prefix/bin:$PATH"

    if command -v brew &>/dev/null; then
        success "Homebrew already installed"
        return
    fi

    info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$("$brew_prefix/bin/brew" shellenv)"
    brew analytics off
    success "Homebrew installed"
}

#=============================================================================
# DOTFILES
#=============================================================================
clone_dotfiles() {
    if [[ -d "$DOTFILES_DIR/.git" ]]; then
        success "Dotfiles already cloned"
        info "Pulling latest changes..."
        git -C "$DOTFILES_DIR" pull --ff-only || warn "Could not fast-forward dotfiles (local changes?)"
        return
    fi

    info "Cloning dotfiles..."
    git clone "$DOTFILES_REPO" "$DOTFILES_DIR"
    success "Dotfiles cloned to $DOTFILES_DIR"
}

#=============================================================================
# SYNC DIRECTORY & THEMES
#=============================================================================
setup_sync_dir() {
    info "Setting up ~/.sync directory..."
    mkdir -p "$SYNC_DIR"

    # Clone themes and resources
    local repos=(
        "dracula/iterm.git:dracula-iterm"
        "dracula/colorls.git:colorls"
        "dracula/alfred:alfred-dracula"
    )

    for repo_spec in "${repos[@]}"; do
        local repo="${repo_spec%:*}"
        local dir="${repo_spec#*:}"

        if [[ -d "$SYNC_DIR/$dir" ]]; then
            info "  $dir already exists, skipping"
        else
            info "  Cloning $dir..."
            git clone "https://github.com/$repo" "$SYNC_DIR/$dir" 2>/dev/null || warn "Failed to clone $dir"
        fi
    done

    success "Sync directory ready"
}

#=============================================================================
# FEATURES
#=============================================================================
# sync.sh owns building the engine and applying, so a fresh install and every
# later sync behave the same.
install_go() {
    if command -v go &>/dev/null; then
        success "Go already installed"
        return
    fi
    info "Installing Go..."
    brew install go
}

choose_profiles() {
    [[ -z "$PROFILES" ]] || return 0
    if [[ -f "$MACHINE_FILE" ]]; then
        success "Keeping the profiles in $MACHINE_FILE"
        return
    fi
    local file
    echo ""
    info "Profiles in $DOTFILES_DIR/profiles (later ones override earlier ones):"
    for file in "$DOTFILES_DIR"/profiles/*.toml; do
        printf '  %-10s %s\n' "$(basename "$file" .toml)" "$(sed -n '1s/^# *//p' "$file")"
    done
    read -r -p "Profiles for this machine, comma-separated (such as base,dev,desktop): " PROFILES </dev/tty || PROFILES=""
    if [[ -z "$PROFILES" ]]; then
        error "No profiles chosen; rerun with --profiles <names>"
        exit 64
    fi
}

setup_features() {
    "$DOTFILES_DIR/sync.sh" build
    if [[ -n "$PROFILES" ]]; then
        local force=()
        [[ -f "$MACHINE_FILE" ]] && force=(--force)
        # ${a[@]+...}: bash 3.2 rejects an empty array under set -u.
        "$DOTFILES_BIN" init --repo "$DOTFILES_DIR" --profiles "$PROFILES" ${force[@]+"${force[@]}"}
    fi
    info "Applying this machine's features..."
    if "$DOTFILES_DIR/sync.sh" apply; then
        success "Features applied"
    else
        warn "dotfiles apply left problems to resolve; run '$DOTFILES_BIN doctor'"
    fi
}

#=============================================================================
# PACKAGES
#=============================================================================
install_packages() {
    info "Installing the enabled features' packages..."
    "$DOTFILES_DIR/sync.sh" brewfile || warn "Some packages may have failed to install; see $DOTFILES_DIR/logs/sync.log"
    # The tools mise's configuration names, such as the default Node LTS.
    if command -v mise &>/dev/null; then
        mise install --yes || warn "mise could not install every tool; run 'mise install'"
    fi
}

#=============================================================================
# LAUNCH AGENTS
#=============================================================================
install_launch_agents() {
    info "Installing LaunchAgents..."

    if [[ -x "$DOTFILES_DIR/bin/dotfiles-install-launchagents.sh" ]]; then
        "$DOTFILES_DIR/bin/dotfiles-install-launchagents.sh"
        success "LaunchAgents installed"
    else
        warn "LaunchAgent installer not found"
    fi
}

#=============================================================================
# MACOS PREFERENCES
#=============================================================================
configure_macos() {
    echo ""
    read -r -p "Configure macOS preferences? (runs config.sh) [y/N] " response </dev/tty || response=""
    if [[ "$response" =~ ^[Yy]$ ]]; then
        info "Configuring macOS preferences..."
        cd "$DOTFILES_DIR"
        zsh -c "./config.sh" || warn "Some preferences may have failed"
        success "macOS configured"
    fi
}

#=============================================================================
# MAIN
#=============================================================================
usage() {
    echo "usage: install.sh [--profiles base,dev,...]"
}

main() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --profiles) PROFILES="${2:-}"; shift 2 || { usage; exit 64; } ;;
            --profiles=*) PROFILES="${1#*=}"; shift ;;
            -h|--help) usage; return 0 ;;
            *) usage; exit 64 ;;
        esac
    done

    echo ""
    echo "======================================"
    echo "  dotfiles installer"
    echo "======================================"
    echo ""

    setup_sudo
    install_xcode_cli
    install_homebrew
    clone_dotfiles
    choose_profiles
    setup_sync_dir
    install_go
    setup_features
    install_packages
    install_launch_agents
    configure_macos

    echo ""
    echo "======================================"
    success "Installation complete!"
    echo "======================================"
    echo ""
    info "Next steps:"
    echo "  1. Restart your terminal"
    echo "  2. Run '~/.dotfiles/sync.sh' to start syncing"
    echo ""
}

# Piped into bash (curl | bash) there is no BASH_SOURCE, which `set -u` rejects.
if [[ "${BASH_SOURCE[0]:-$0}" == "$0" ]]; then main "$@"; fi
