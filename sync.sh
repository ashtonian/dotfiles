#!/usr/bin/env bash
#
# dotfiles-sync: Auto-commit and push dotfiles changes
# This script is designed to be run manually or via LaunchAgent
#

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.dotfiles}"
LOG_DIR="${DOTFILES_DIR}/logs"
LOG_FILE="${LOG_DIR}/sync.log"
MAX_LOG_SIZE=1048576  # 1MB

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Rotate log if too large
if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat --printf="%s" "$LOG_FILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Check if we're online
check_connectivity() {
    if ! ping -c 1 -W 2 github.com &>/dev/null; then
        log "WARN: No network connectivity, skipping sync"
        return 1
    fi
    return 0
}

# Run mackup backup to capture app configs
run_mackup_backup() {
    if command -v mackup &>/dev/null; then
        log "INFO: Running mackup backup..."
        if mackup backup --force 2>&1 | tee -a "$LOG_FILE"; then
            log "INFO: Mackup backup complete"
        else
            log "WARN: Mackup backup failed"
        fi
    else
        log "INFO: mackup not installed, skipping app config backup"
    fi
}

# Main sync function
sync_dotfiles() {
    cd "$DOTFILES_DIR" || {
        log "ERROR: Cannot cd to $DOTFILES_DIR"
        exit 1
    }

    # Ensure we're in a git repo
    if [[ ! -d ".git" ]]; then
        log "ERROR: $DOTFILES_DIR is not a git repository"
        exit 1
    fi

    log "Starting dotfiles sync..."

    # Fetch latest changes
    if ! git fetch origin 2>&1 | tee -a "$LOG_FILE"; then
        log "WARN: Failed to fetch from origin"
    fi

    # Check for local changes
    if git diff-index --quiet HEAD -- 2>/dev/null; then
        log "INFO: No local changes to commit"
    else
        # Stage all changes
        git add -A

        # Create commit with timestamp
        local commit_msg="auto: sync $(date '+%Y-%m-%d %H:%M') from $(hostname -s)"
        if git commit -m "$commit_msg" 2>&1 | tee -a "$LOG_FILE"; then
            log "INFO: Committed local changes"
        else
            log "WARN: Failed to commit changes"
        fi
    fi

    # Check for untracked files
    local untracked
    untracked=$(git ls-files --others --exclude-standard)
    if [[ -n "$untracked" ]]; then
        log "INFO: Found untracked files:"
        echo "$untracked" | tee -a "$LOG_FILE"
        git add -A
        git commit -m "auto: add new files $(date '+%Y-%m-%d %H:%M')" 2>&1 | tee -a "$LOG_FILE" || true
    fi

    # Pull with rebase to get remote changes
    if git pull --rebase origin "$(git rev-parse --abbrev-ref HEAD)" 2>&1 | tee -a "$LOG_FILE"; then
        log "INFO: Pulled latest changes"
    else
        log "WARN: Pull failed, may need manual intervention"
        # Abort rebase if in progress
        git rebase --abort 2>/dev/null || true
    fi

    # Push changes
    if git push origin "$(git rev-parse --abbrev-ref HEAD)" 2>&1 | tee -a "$LOG_FILE"; then
        log "INFO: Pushed changes to origin"
    else
        log "WARN: Push failed, will retry on next sync"
    fi

    log "Sync complete"
}

# Run stow to ensure symlinks are current
run_stow() {
    if command -v stow &>/dev/null; then
        log "INFO: Running stow to update symlinks..."
        cd "$DOTFILES_DIR/stow" || return

        for package in */; do
            package="${package%/}"
            if [[ -d "$package" ]]; then
                stow -v -R -t "$HOME" "$package" 2>&1 | tee -a "$LOG_FILE" || {
                    log "WARN: stow failed for package $package"
                }
            fi
        done
    else
        log "INFO: stow not installed, skipping symlink update"
    fi
}

# Main
main() {
    case "${1:-sync}" in
        sync)
            check_connectivity || exit 0
            run_mackup_backup
            sync_dotfiles
            ;;
        stow)
            run_stow
            ;;
        all)
            check_connectivity || exit 0
            run_mackup_backup
            sync_dotfiles
            run_stow
            ;;
        *)
            echo "Usage: $0 {sync|stow|all}"
            exit 1
            ;;
    esac
}

main "$@"
