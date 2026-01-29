#!/usr/bin/env bash
#===============================================================================
# dotfiles-update.sh - Automated update script for dotfiles and system packages
#===============================================================================
#
# DESCRIPTION:
#   Updates Homebrew packages, Zinit plugins, and syncs dotfiles.
#   Designed to run weekly via LaunchAgent or manually.
#
# USAGE:
#   dotfiles-update.sh [options]
#
# OPTIONS:
#   --brew      Update Homebrew only
#   --zinit     Update Zinit plugins only
#   --sync      Sync dotfiles only
#   --all       Update everything (default)
#   --quiet     Suppress non-error output
#   --help      Show this help
#
# LAUNCHAGENT:
#   Installed at: ~/Library/LaunchAgents/com.dotfiles.update.plist
#   Runs every Friday at 9:00 AM
#
#===============================================================================

set -euo pipefail

#===============================================================================
# CONFIGURATION
#===============================================================================
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.dotfiles}"
LOG_DIR="${DOTFILES_DIR}/logs"
LOG_FILE="${LOG_DIR}/update.log"
QUIET=false

# Ensure log directory exists
mkdir -p "$LOG_DIR"

#===============================================================================
# LOGGING
#===============================================================================
log() {
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$timestamp] $*" >> "$LOG_FILE"
    [[ "$QUIET" == "false" ]] && echo "$*"
}

log_error() {
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$timestamp] ERROR: $*" >> "$LOG_FILE"
    echo "ERROR: $*" >&2
}

#===============================================================================
# UPDATE FUNCTIONS
#===============================================================================

update_brew() {
    log "=== Updating Homebrew ==="

    if ! command -v brew &>/dev/null; then
        log_error "Homebrew not found"
        return 1
    fi

    log "Running brew update..."
    brew update 2>&1 | tee -a "$LOG_FILE" || true

    log "Running brew upgrade..."
    brew upgrade 2>&1 | tee -a "$LOG_FILE" || true

    log "Running brew cleanup..."
    brew cleanup --prune=7 2>&1 | tee -a "$LOG_FILE" || true

    log "Checking brew doctor..."
    brew doctor 2>&1 | tee -a "$LOG_FILE" || true

    log "Homebrew update complete"
}

update_zinit() {
    log "=== Updating Zinit plugins ==="

    local zinit_home="${XDG_DATA_HOME:-$HOME/.local/share}/zinit/zinit.git"

    if [[ ! -d "$zinit_home" ]]; then
        log_error "Zinit not found at $zinit_home"
        return 1
    fi

    # Update zinit itself
    log "Updating zinit core..."
    (cd "$zinit_home" && git pull --quiet) 2>&1 | tee -a "$LOG_FILE" || true

    # Update all plugins via zsh
    log "Updating zinit plugins..."
    zsh -ic 'zinit update --all --quiet' 2>&1 | tee -a "$LOG_FILE" || true

    log "Zinit update complete"
}

sync_dotfiles() {
    log "=== Syncing dotfiles ==="

    if [[ ! -d "$DOTFILES_DIR/.git" ]]; then
        log_error "Dotfiles directory is not a git repository"
        return 1
    fi

    # Use the sync script if available
    if [[ -x "$DOTFILES_DIR/sync.sh" ]]; then
        "$DOTFILES_DIR/sync.sh" sync 2>&1 | tee -a "$LOG_FILE"
    else
        cd "$DOTFILES_DIR"

        log "Fetching remote changes..."
        git fetch origin 2>&1 | tee -a "$LOG_FILE" || true

        log "Checking for local changes..."
        if ! git diff-index --quiet HEAD -- 2>/dev/null; then
            git add -A
            git commit -m "auto: sync $(date '+%Y-%m-%d %H:%M') from $(hostname -s)" 2>&1 | tee -a "$LOG_FILE" || true
        fi

        log "Pulling remote changes..."
        git pull --rebase origin "$(git rev-parse --abbrev-ref HEAD)" 2>&1 | tee -a "$LOG_FILE" || true

        log "Pushing changes..."
        git push origin "$(git rev-parse --abbrev-ref HEAD)" 2>&1 | tee -a "$LOG_FILE" || true
    fi

    log "Dotfiles sync complete"
}

update_all() {
    log "======================================"
    log "Starting full system update"
    log "======================================"

    update_brew
    echo ""
    update_zinit
    echo ""
    sync_dotfiles

    log "======================================"
    log "Full update complete!"
    log "======================================"
}

#===============================================================================
# HELP
#===============================================================================
show_help() {
    sed -n '/^#===============================================================================/,/^#===============================================================================/p' "$0" | head -25 | tail -22 | sed 's/^# //'
}

#===============================================================================
# MAIN
#===============================================================================
main() {
    local action="all"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --brew)     action="brew"; shift ;;
            --zinit)    action="zinit"; shift ;;
            --sync)     action="sync"; shift ;;
            --all)      action="all"; shift ;;
            --quiet)    QUIET=true; shift ;;
            --help|-h)  show_help; exit 0 ;;
            *)          log_error "Unknown option: $1"; show_help; exit 1 ;;
        esac
    done

    case "$action" in
        brew)   update_brew ;;
        zinit)  update_zinit ;;
        sync)   sync_dotfiles ;;
        all)    update_all ;;
    esac
}

main "$@"
