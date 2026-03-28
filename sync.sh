#!/usr/bin/env bash
#
# dotfiles-sync: Auto-sync dotfiles, app configs, and auxiliary repos
# This script is designed to be run manually or via LaunchAgent
#
# Syncs:
#   1. ~/.dotfiles (this repo)
#   2. All git repos in ~/.sync/ (mackup, themes, etc.)
#   3. Brewfile (installs missing shared packages, does NOT overwrite)
#   4. App configs via mackup (copy mode, isolated per hostname)
#

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.dotfiles}"
SYNC_DIR="${SYNC_DIR:-$HOME/.sync}"
LOG_DIR="${DOTFILES_DIR}/logs"
LOG_FILE="${LOG_DIR}/sync.log"
MAX_LOG_SIZE=1048576  # 1MB

# Ensure directories exist
mkdir -p "$LOG_DIR" "$SYNC_DIR"

# Rotate log if too large (timestamped to avoid multi-machine collisions)
if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat --printf="%s" "$LOG_FILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]]; then
    mv "$LOG_FILE" "${LOG_FILE}.$(date +%s).old"
fi
# Clean up old rotated logs (keep only 3 most recent)
for old_log in $(ls -t "${LOG_FILE}".*.old 2>/dev/null | tail -n +4); do
    rm -f "$old_log"
done

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

#=============================================================================
# BREWFILE SYNC
#=============================================================================
# Installs packages from the curated shared Brewfile (and Brewfile.local if present).
# Does NOT overwrite the Brewfile — edit it manually to add/remove shared packages.
# Use Brewfile.local (gitignored) for machine-specific packages.
sync_brewfile() {
    if command -v brew &>/dev/null; then
        local brewfile="${DOTFILES_DIR}/Brewfile"
        local brewfile_local="${DOTFILES_DIR}/Brewfile.local"

        # Install missing packages from shared Brewfile
        if [[ -f "$brewfile" ]]; then
            log "INFO: Installing missing packages from shared Brewfile..."
            brew bundle --no-lock --file="$brewfile" 2>&1 | tee -a "$LOG_FILE" || {
                log "WARN: Some shared Brewfile packages failed to install"
            }
        fi

        # Install from machine-specific Brewfile.local if it exists
        if [[ -f "$brewfile_local" ]]; then
            log "INFO: Installing from Brewfile.local..."
            brew bundle --no-lock --file="$brewfile_local" 2>&1 | tee -a "$LOG_FILE" || {
                log "WARN: Some Brewfile.local packages failed to install"
            }
        fi
    else
        log "INFO: brew not installed, skipping Brewfile sync"
    fi
}

#=============================================================================
# MACKUP BACKUP (copy mode, per-host isolation)
#=============================================================================
# Backs up to ~/.sync/mackup/$(hostname -s)/ to prevent multi-machine overwrites.
run_mackup_backup() {
    if command -v mackup &>/dev/null; then
        local cfg="$HOME/.mackup.cfg"
        local host_dir="mackup/$(hostname -s)"

        # Ensure host-specific backup directory exists
        mkdir -p "$HOME/.sync/$host_dir"

        # Temporarily update mackup config to use host-specific directory
        if [[ -f "$cfg" ]]; then
            sed -i.bak "s|^directory = .*|directory = $host_dir|" "$cfg"
        fi

        log "INFO: Running mackup backup (copy mode -> $host_dir)..."
        if mackup backup --force 2>&1 | tee -a "$LOG_FILE"; then
            log "INFO: Mackup backup complete"
        else
            log "WARN: Mackup backup failed"
        fi

        # Restore original config
        if [[ -f "${cfg}.bak" ]]; then
            mv "${cfg}.bak" "$cfg"
        fi
    else
        log "INFO: mackup not installed, skipping app config backup"
    fi
}

#=============================================================================
# GIT REPO SYNC (generic)
#=============================================================================
sync_git_repo() {
    local repo_dir="$1"
    local repo_name
    repo_name=$(basename "$repo_dir")

    cd "$repo_dir" || {
        log "ERROR: Cannot cd to $repo_dir"
        return 1
    }

    # Ensure we're in a git repo
    if [[ ! -d ".git" ]]; then
        log "WARN: $repo_dir is not a git repository, skipping"
        return 0
    fi

    log "INFO: Syncing $repo_name..."

    # Check if remote exists
    if ! git remote get-url origin &>/dev/null; then
        log "INFO: $repo_name has no remote, committing locally only"
        # Just commit local changes
        if ! git diff-index --quiet HEAD -- 2>/dev/null || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
            git add -A
            git commit -m "auto: sync $(date '+%Y-%m-%d %H:%M') from $(hostname -s)" 2>&1 | tee -a "$LOG_FILE" || true
        fi
        return 0
    fi

    # Fetch latest changes
    git fetch origin 2>&1 | tee -a "$LOG_FILE" || log "WARN: Failed to fetch $repo_name"

    # Check for local changes (staged, unstaged, and untracked)
    if ! git diff-index --quiet HEAD -- 2>/dev/null || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
        git add -A
        local commit_msg="auto: sync $(date '+%Y-%m-%d %H:%M') from $(hostname -s)"
        git commit -m "$commit_msg" 2>&1 | tee -a "$LOG_FILE" || true
        log "INFO: Committed local changes in $repo_name"
    fi

    # Get current branch
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

    # Pull with rebase (stash if needed)
    local stashed=false
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        git stash push -m "auto-stash for sync" 2>&1 | tee -a "$LOG_FILE"
        stashed=true
    fi

    if git pull --rebase origin "$branch" 2>&1 | tee -a "$LOG_FILE"; then
        log "INFO: Pulled latest changes for $repo_name"
    else
        log "WARN: Pull failed for $repo_name, aborting rebase"
        git rebase --abort 2>/dev/null || true
    fi

    if [[ "$stashed" == "true" ]]; then
        git stash pop 2>&1 | tee -a "$LOG_FILE" || log "WARN: Failed to pop stash"
    fi

    # Push changes with retry (handles multi-machine race conditions)
    local max_retries=3
    local retry_delay=30
    local pushed=false

    for attempt in $(seq 1 $max_retries); do
        if git push origin "$branch" 2>&1 | tee -a "$LOG_FILE"; then
            log "INFO: Pushed $repo_name to origin"
            pushed=true
            break
        else
            if [[ $attempt -lt $max_retries ]]; then
                log "WARN: Push failed for $repo_name (attempt $attempt/$max_retries), retrying in ${retry_delay}s..."
                sleep "$retry_delay"
                git pull --rebase origin "$branch" 2>&1 | tee -a "$LOG_FILE" || {
                    git rebase --abort 2>/dev/null || true
                    log "WARN: Rebase failed during retry for $repo_name"
                    break
                }
                retry_delay=$((retry_delay * 2))
            fi
        fi
    done

    if [[ "$pushed" != "true" ]]; then
        log "WARN: Push failed for $repo_name after $max_retries attempts, will retry next sync"
    fi
}

#=============================================================================
# SYNC ALL REPOS IN ~/.sync/
#=============================================================================
sync_auxiliary_repos() {
    log "INFO: Scanning $SYNC_DIR for git repos..."

    for dir in "$SYNC_DIR"/*/; do
        [[ -d "$dir" ]] || continue
        if [[ -d "${dir}.git" ]]; then
            sync_git_repo "$dir"
        fi
    done
}

#=============================================================================
# SYNC DOTFILES REPO
#=============================================================================
sync_dotfiles() {
    sync_git_repo "$DOTFILES_DIR"
}

#=============================================================================
# STOW SYMLINKS
#=============================================================================
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

#=============================================================================
# MAIN
#=============================================================================
main() {
    case "${1:-sync}" in
        sync)
            check_connectivity || exit 0
            log "========== Starting full sync =========="
            sync_brewfile
            run_mackup_backup
            sync_dotfiles
            sync_auxiliary_repos
            log "========== Sync complete =========="
            ;;
        dotfiles)
            check_connectivity || exit 0
            sync_dotfiles
            ;;
        repos)
            check_connectivity || exit 0
            sync_auxiliary_repos
            ;;
        stow)
            run_stow
            ;;
        brewfile)
            sync_brewfile
            ;;
        mackup)
            run_mackup_backup
            ;;
        all)
            check_connectivity || exit 0
            log "========== Starting full sync + stow =========="
            sync_brewfile
            run_mackup_backup
            sync_dotfiles
            sync_auxiliary_repos
            run_stow
            log "========== Sync complete =========="
            ;;
        *)
            echo "Usage: $0 {sync|dotfiles|repos|stow|brewfile|mackup|all}"
            echo ""
            echo "Commands:"
            echo "  sync      - Full sync: brewfile + mackup + dotfiles + ~/.sync repos"
            echo "  dotfiles  - Sync only ~/.dotfiles"
            echo "  repos     - Sync only repos in ~/.sync/"
            echo "  stow      - Run stow to update symlinks"
            echo "  brewfile  - Install missing packages from shared Brewfile"
            echo "  mackup    - Run mackup backup (per-host isolated)"
            echo "  all       - Full sync + stow"
            exit 1
            ;;
    esac
}

main "$@"
