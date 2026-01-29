#!/usr/bin/env bash
#===============================================================================
# dotfiles-install-launchagents.sh - Install all dotfiles LaunchAgents
#===============================================================================
#
# DESCRIPTION:
#   Installs LaunchAgents for automated dotfiles management:
#   - com.dotfiles.sync   : Syncs dotfiles every 4 hours
#   - com.dotfiles.update : Updates brew/zinit weekly (Fridays 9 AM)
#
# USAGE:
#   dotfiles-install-launchagents.sh [options]
#
# OPTIONS:
#   --sync-only    Install only the sync agent
#   --update-only  Install only the update agent
#   --uninstall    Remove all dotfiles LaunchAgents
#   --status       Show status of installed agents
#   --help         Show this help
#
#===============================================================================

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.dotfiles}"
LAUNCH_AGENTS_SRC="$DOTFILES_DIR/launchagents"
LAUNCH_AGENTS_DST="$HOME/Library/LaunchAgents"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

#===============================================================================
# FUNCTIONS
#===============================================================================

install_agent() {
    local name="$1"
    local src="$LAUNCH_AGENTS_SRC/${name}.plist"
    local dst="$LAUNCH_AGENTS_DST/${name}.plist"

    if [[ ! -f "$src" ]]; then
        log_error "Source plist not found: $src"
        return 1
    fi

    # Create destination directory
    mkdir -p "$LAUNCH_AGENTS_DST"

    # Unload existing agent if running
    if launchctl list 2>/dev/null | grep -q "$name"; then
        log_info "Unloading existing $name..."
        launchctl unload "$dst" 2>/dev/null || true
    fi

    # Copy and process the plist (replace $HOME with actual path)
    log_info "Installing $name..."
    sed "s|\$HOME|$HOME|g" "$src" > "$dst"

    # Load the agent
    log_info "Loading $name..."
    if launchctl load "$dst"; then
        log_info "$name installed and running"
    else
        log_error "Failed to load $name"
        return 1
    fi
}

uninstall_agent() {
    local name="$1"
    local dst="$LAUNCH_AGENTS_DST/${name}.plist"

    if [[ -f "$dst" ]]; then
        log_info "Unloading $name..."
        launchctl unload "$dst" 2>/dev/null || true
        rm -f "$dst"
        log_info "$name removed"
    else
        log_warn "$name not installed"
    fi
}

show_status() {
    echo ""
    echo "=== Dotfiles LaunchAgents Status ==="
    echo ""

    for agent in com.dotfiles.sync com.dotfiles.update; do
        local dst="$LAUNCH_AGENTS_DST/${agent}.plist"
        printf "%-25s: " "$agent"

        if [[ -f "$dst" ]]; then
            if launchctl list 2>/dev/null | grep -q "$agent"; then
                echo -e "${GREEN}Running${NC}"
            else
                echo -e "${YELLOW}Installed (not running)${NC}"
            fi
        else
            echo -e "${RED}Not installed${NC}"
        fi
    done

    echo ""
    echo "=== Recent Activity ==="
    echo ""

    if [[ -f "$DOTFILES_DIR/logs/sync.log" ]]; then
        echo "Last sync:"
        tail -3 "$DOTFILES_DIR/logs/sync.log" 2>/dev/null || echo "  No logs yet"
    fi

    if [[ -f "$DOTFILES_DIR/logs/update.log" ]]; then
        echo ""
        echo "Last update:"
        tail -3 "$DOTFILES_DIR/logs/update.log" 2>/dev/null || echo "  No logs yet"
    fi

    echo ""
}

show_help() {
    head -25 "$0" | tail -20 | sed 's/^# //'
}

install_all() {
    echo ""
    echo "=== Installing Dotfiles LaunchAgents ==="
    echo ""

    install_agent "com.dotfiles.sync"
    install_agent "com.dotfiles.update"

    echo ""
    echo "=== Installation Complete ==="
    echo ""
    echo "Sync agent:   Runs every 4 hours"
    echo "Update agent: Runs every Friday at 9 AM"
    echo ""
    echo "Commands:"
    echo "  Check status:    $0 --status"
    echo "  Manual sync:     ~/.dotfiles/sync.sh sync"
    echo "  Manual update:   ~/.dotfiles/bin/dotfiles-update.sh --all"
    echo "  Trigger sync:    launchctl start com.dotfiles.sync"
    echo "  Trigger update:  launchctl start com.dotfiles.update"
    echo ""
}

uninstall_all() {
    echo ""
    echo "=== Removing Dotfiles LaunchAgents ==="
    echo ""

    uninstall_agent "com.dotfiles.sync"
    uninstall_agent "com.dotfiles.update"

    echo ""
    echo "All LaunchAgents removed."
    echo ""
}

#===============================================================================
# MAIN
#===============================================================================

main() {
    case "${1:-}" in
        --sync-only)
            install_agent "com.dotfiles.sync"
            ;;
        --update-only)
            install_agent "com.dotfiles.update"
            ;;
        --uninstall)
            uninstall_all
            ;;
        --status)
            show_status
            ;;
        --help|-h)
            show_help
            ;;
        "")
            install_all
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
