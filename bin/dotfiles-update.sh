#!/usr/bin/env bash
#===============================================================================
# dotfiles-update.sh - Automated update script for dotfiles and system packages
#===============================================================================
#
# DESCRIPTION:
#   Updates Homebrew packages, mise's tools, Zinit plugins, and syncs dotfiles.
#   Designed to run weekly via LaunchAgent or manually.
#
# USAGE:
#   dotfiles-update.sh [options]
#
# OPTIONS:
#   --brew      Update Homebrew only
#   --mise      Install the tools mise's configuration names and lacks only
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
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$timestamp] $*" >> "$LOG_FILE"
    if [[ "$QUIET" == false ]]; then printf '%s\n' "$*"; fi
}

log_error() {
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$timestamp] ERROR: $*" >> "$LOG_FILE"
    echo "ERROR: $*" >&2
}

#===============================================================================
# UPDATE FUNCTIONS
#===============================================================================

run_command() {
    if [[ "$QUIET" == true ]]; then
        if "$@" >> "$LOG_FILE" 2>&1; then return 0; else
            local status=$?
            log_error "Command failed (exit $status); see $LOG_FILE"
            return "$status"
        fi
    else
        "$@" 2>&1 | tee -a "$LOG_FILE"
    fi
}

update_brew() {
    log "=== Updating Homebrew ==="

    if ! command -v brew &>/dev/null; then
        log_error "Homebrew not found"
        return 1
    fi

    log "Running brew update..."
    run_command brew update || return

    log "Running brew upgrade..."
    run_command brew upgrade || return

    log "Running brew cleanup..."
    run_command brew cleanup --prune=7 || return

    log "Checking brew doctor..."
    run_command brew doctor || return

    log "Homebrew update complete"
}

# The tools mise's configuration names, such as the shared default Node LTS
# that agents and LaunchAgents reach through mise's shims: install what is
# missing, which includes a new LTS once one is released.
update_mise() {
    log "=== Installing mise tools ==="
    if ! command -v mise >/dev/null; then
        log "mise is not installed; skipping"
        return 0
    fi
    run_command mise install --yes || return
    log "mise tools up to date"
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
    run_command git -C "$zinit_home" pull --ff-only --quiet || return

    # Update all plugins via zsh
    log "Updating zinit plugins..."
    run_command zsh -ic 'zinit update --all --quiet' || return

    log "Zinit update complete"
}

sync_dotfiles() {
    log "=== Syncing dotfiles ==="

    if [[ ! -d "$DOTFILES_DIR/.git" ]]; then
        log_error "Dotfiles directory is not a git repository"
        return 1
    fi

    if [[ ! -x "$DOTFILES_DIR/sync.sh" ]]; then
        log_error "Sync script is missing or not executable"
        return 1
    fi
    run_command "$DOTFILES_DIR/sync.sh" sync || return

    log "Dotfiles sync complete"
}

update_all() {
    log "======================================"
    log "Starting full system update"
    log "======================================"

    update_brew || return
    update_mise || return
    update_zinit || return
    sync_dotfiles || return

    log "======================================"
    log "Full update complete!"
    log "======================================"
}

#===============================================================================
# HELP
#===============================================================================
show_help() {
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
}

#===============================================================================
# MAIN
#===============================================================================
main() {
    local action="all"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --brew)     action="brew"; shift ;;
            --mise)     action="mise"; shift ;;
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
        mise)   update_mise ;;
        zinit)  update_zinit ;;
        sync)   sync_dotfiles ;;
        all)    update_all ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
