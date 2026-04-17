#!/usr/bin/env bash
#
# dotfiles installer - Bootstrap a new macOS machine
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ashtonian/dotfiles/master/install.sh | bash
#
# Or clone first:
#   git clone https://github.com/ashtonian/dotfiles.git ~/.dotfiles
#   ~/.dotfiles/install.sh
#

set -euo pipefail

#=============================================================================
# CONFIGURATION
#=============================================================================
DOTFILES_DIR="${HOME}/.dotfiles"
DOTFILES_REPO="https://github.com/ashtonian/dotfiles.git"
SYNC_DIR="${HOME}/.sync"

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
    read -r -p "Enable passwordless sudo? [y/N] " response
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
    export PATH="/opt/homebrew/bin:$PATH"

    if command -v brew &>/dev/null; then
        success "Homebrew already installed"
        return
    fi

    info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
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
        cd "$DOTFILES_DIR" && git pull
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

    # Setup colorls theme
    if [[ -f "$SYNC_DIR/colorls/dark_colors.yaml" ]]; then
        mkdir -p "$HOME/.config/colorls"
        cp "$SYNC_DIR/colorls/dark_colors.yaml" "$HOME/.config/colorls/dark_colors.yaml"
    fi

    # Initialize mackup repo if not exists
    if [[ ! -d "$SYNC_DIR/mackup/.git" ]]; then
        info "Initializing mackup backup repo..."
        mkdir -p "$SYNC_DIR/mackup"
        cd "$SYNC_DIR/mackup"
        git init
        git commit --allow-empty -m "Initial commit"
    fi

    success "Sync directory ready"
}

#=============================================================================
# STOW PACKAGES
#=============================================================================
setup_stow() {
    if ! command -v stow &>/dev/null; then
        info "Installing stow..."
        brew install stow
    fi

    info "Setting up stow packages..."
    cd "$DOTFILES_DIR/stow"

    for package in */; do
        package="${package%/}"
        info "  Stowing $package..."
        stow -v -R -t "$HOME" "$package" 2>&1 | grep -v "^LINK:" || true
    done

    success "Stow packages linked"
}

#=============================================================================
# BREW BUNDLE
#=============================================================================
install_packages() {
    info "Installing packages from Brewfile..."
    cd "$DOTFILES_DIR"

    if [[ -f "Brewfile" ]]; then
        brew bundle --no-lock || warn "Some packages may have failed to install"
        success "Packages installed"
    else
        warn "No Brewfile found, skipping package installation"
    fi
}

#=============================================================================
# MACKUP
#=============================================================================
setup_mackup() {
    if ! command -v mackup &>/dev/null; then
        info "Installing mackup..."
        brew install mackup
    fi

    info "Mackup configured (run 'mackup restore' to restore app configs)"
    success "Mackup ready"
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
    read -r -p "Configure macOS preferences? (runs config.sh) [y/N] " response
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
main() {
    echo ""
    echo "======================================"
    echo "  dotfiles installer"
    echo "======================================"
    echo ""

    setup_sudo
    install_xcode_cli
    install_homebrew
    clone_dotfiles
    setup_sync_dir
    install_packages
    setup_stow
    setup_mackup
    install_launch_agents
    configure_macos

    echo ""
    echo "======================================"
    success "Installation complete!"
    echo "======================================"
    echo ""
    info "Next steps:"
    echo "  1. Restart your terminal"
    echo "  2. Run 'mackup restore' if you have existing app configs"
    echo "  3. Run '~/.dotfiles/sync.sh' to start syncing"
    echo ""
}

main "$@"
