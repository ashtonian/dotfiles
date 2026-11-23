#!/usr/bin/env bash
#===============================================================================
# dotfiles-update.sh - Automated update script for dotfiles and system packages
#===============================================================================
#
# DESCRIPTION:
#   Updates Homebrew packages, the Go pin (on the canary machine) and Zinit
#   plugins, then syncs dotfiles, which installs what mise's configuration names.
#   Each stage runs whatever the others did and reports its own result; the run
#   fails when any stage failed. Upgrades that need root are left for a
#   terminal, with a warning, when the run cannot ask for a password.
#   Designed to run weekly via LaunchAgent or manually.
#
# USAGE:
#   dotfiles-update.sh [options]
#
# OPTIONS:
#   --brew      Update Homebrew only
#   --go        Move the Go pin to its minor's newest patch only (mise.canary)
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

# shellcheck source=lib_sh/rotate-log.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib_sh/rotate-log.sh"
# shellcheck source=lib_sh/brew-root.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib_sh/brew-root.sh"

#===============================================================================
# CONFIGURATION
#===============================================================================
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.dotfiles}"
LOG_DIR="${DOTFILES_DIR}/logs"
LOG_FILE="${LOG_DIR}/update.log"
QUIET=false
# Set by update_brew: the environment of every brew command after `brew
# update`, and whether this run can ask for a password.
BREW_ENV=()
UNATTENDED=false

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

log_warn() { log "WARN: $*"; }

log_error() {
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$timestamp] ERROR: $*" >> "$LOG_FILE"
    echo "ERROR: $*" >&2
}

#===============================================================================
# UPDATE FUNCTIONS
#===============================================================================

# run_command CMD...: run CMD with its output in the log (and on stdout unless
# --quiet) and return its status. Callers log what a failure means.
run_command() {
    if [[ "$QUIET" == true ]]; then
        "$@" >> "$LOG_FILE" 2>&1
    else
        "$@" 2>&1 | tee -a "$LOG_FILE"
    fi
}

# upgrade_outdated formula|cask: upgrade every outdated formula or cask in one
# brew run. When that run fails, each one still outdated is retried alone, so
# one that cannot build or install (a formula that needs a newer Xcode stops
# the whole run) does not hold back the others. Unattended, an item that fails
# for want of root (HOMEBREW_NO_SUDO, or a permission error) is left for a
# terminal with a warning; any other failure fails the step.
upgrade_outdated() {
    local kind=$1
    log "Running brew upgrade --$kind..."
    if run_command env "${BREW_ENV[@]}" brew upgrade --"$kind"; then
        return 0
    fi
    local outdated
    if ! outdated=$(env "${BREW_ENV[@]}" brew outdated --"$kind" --json=v2 2>>"$LOG_FILE" |
        jq -r '((.formulae // []) + (.casks // []))[] | select(.pinned != true) | .name'); then
        log_error "brew upgrade --$kind failed, and listing what is still outdated failed too; see $LOG_FILE"
        return 1
    fi
    if [[ -z "$outdated" ]]; then
        log_error "brew upgrade --$kind failed, though nothing is left outdated; see its output in $LOG_FILE"
        return 1
    fi

    local name status out root=() failed=()
    out=$(mktemp "${TMPDIR:-/tmp}/dotfiles-update.XXXXXX") || return
    while IFS= read -r name; do
        log "Retrying brew upgrade --$kind $name alone..."
        status=0
        env "${BREW_ENV[@]}" brew upgrade --"$kind" "$name" </dev/null >"$out" 2>&1 || status=$?
        cat "$out" >> "$LOG_FILE"
        if [[ "$QUIET" == false ]]; then cat "$out"; fi
        if [[ $status -eq 0 ]]; then
            continue
        fi
        if [[ $UNATTENDED == true ]] && grep -qE 'HOMEBREW_NO_SUDO|Permission denied' "$out"; then
            root+=("$name")
        else
            failed+=("$name")
        fi
    done <<<"$outdated"
    rm -f "$out"

    if [[ ${#root[@]} -gt 0 ]]; then
        log_warn "Left ${root[*]} for a terminal: upgrading them needs root and this run cannot ask for a password; run: brew upgrade --$kind ${root[*]}"
    fi
    if [[ ${#failed[@]} -gt 0 ]]; then
        log_error "brew upgrade --$kind failed for ${failed[*]}; see $LOG_FILE"
        return 1
    fi
}

update_brew() {
    log "=== Updating Homebrew ==="

    if ! command -v brew &>/dev/null; then
        log_error "Homebrew not found"
        return 1
    fi

    BREW_ENV=(HOMEBREW_NO_AUTO_UPDATE=1)
    UNATTENDED=false
    if ! brew_root_available; then
        UNATTENDED=true
        BREW_ENV+=(HOMEBREW_NO_SUDO=1)
        log "No terminal to ask for a password in and no passwordless sudo: upgrades that need root wait for a terminal"
    fi

    # Every step runs whatever the one before did: a failed fetch still leaves
    # the last one's upgrades, and cleanup is what bounds Homebrew's download
    # cache and old versions.
    local status=0
    log "Running brew update..."
    if ! run_command brew update; then
        log_error "brew update failed; upgrading against the formulae and casks fetched before"
        status=1
    fi
    upgrade_outdated formula || status=1
    upgrade_outdated cask || status=1

    log "Running brew cleanup..."
    if ! run_command env "${BREW_ENV[@]}" brew cleanup --prune=7; then
        log_error "brew cleanup failed; see $LOG_FILE"
        status=1
    fi

    # brew doctor exits 1 for any warning, such as an Xcode older than the one
    # Homebrew wants. Those need a person and never fail the update.
    log "Checking brew doctor..."
    if ! run_command env "${BREW_ENV[@]}" brew doctor; then
        log_warn "brew doctor reported problems (above); they need a person and do not fail the update"
    fi

    if [[ $status -ne 0 ]]; then
        log_error "Homebrew update finished with failures (above)"
        return "$status"
    fi
    log "Homebrew update complete"
}

# machine_setting VAR: a setting's value on this machine, as `dotfiles apply`
# generated it, unless the environment already sets VAR. Read in a subshell, so
# the other settings stay out of this run's environment.
machine_setting() {
    local generated="$HOME/.config/dotfiles/generated/env.sh"
    (
        # shellcheck source=/dev/null
        if [[ -r "$generated" ]]; then . "$generated" >/dev/null 2>&1; fi
        printf '%s' "${!1:-}"
    )
}

# The Go release every machine builds with is pinned in the tracked mise
# config. On the canary machine (setting mise.canary), move the pin to the
# newest patch of its minor: install it, check that it runs, and commit the one
# line; the sync that follows publishes it, and every other machine's next sync
# installs it. A new minor changes the compiler and runtime under every
# benchmark, so it stays a deliberate edit.
update_go_pin() {
    log "=== Checking the Go pin ==="
    local canary host
    canary=$(machine_setting DOTFILES_MISE_CANARY)
    host=$(scutil --get LocalHostName 2>/dev/null || hostname -s)
    if [[ -z "$canary" || "$canary" != "$host" ]]; then
        log "The Go pin moves on the canary machine only (setting mise.canary: '$canary'; this is $host)"
        return 0
    fi
    if ! command -v mise >/dev/null; then
        log_error "mise is not installed; cannot check the Go pin"
        return 1
    fi

    local rel="features/tool.mise/home/.config/mise/conf.d/dotfiles.toml"
    local file="$DOTFILES_DIR/$rel" pin latest branch
    pin=$(sed -nE 's/^go = "([0-9]+\.[0-9]+\.[0-9]+)"$/\1/p' "$file")
    if [[ ! "$pin" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "No single go = \"X.Y.Z\" line in $file"
        return 1
    fi
    latest=$(mise latest "go@${pin%.*}") || { log_error "mise latest go@${pin%.*} failed"; return 1; }
    if [[ ! "$latest" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "mise latest go@${pin%.*} printed '$latest', not a Go release"
        return 1
    fi
    if [[ "$latest" == "$pin" || "$(printf '%s\n' "$pin" "$latest" | sort -V | tail -n 1)" != "$latest" ]]; then
        log "Go $pin is the newest ${pin%.*} release"
        return 0
    fi

    # Commit only onto a branch sync publishes, and never over an edit in progress.
    branch=$(git -C "$DOTFILES_DIR" symbolic-ref --quiet --short HEAD) || branch=""
    if [[ -z "$branch" || "$(git -C "$DOTFILES_DIR" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)" != "origin/$branch" ]]; then
        log "WARN: Go $latest is out, but $DOTFILES_DIR is not on a branch that tracks origin; leaving the pin at $pin"
        return 0
    fi
    if [[ -n "$(git -C "$DOTFILES_DIR" status --porcelain -- "$rel")" ]]; then
        log "WARN: Go $latest is out, but $rel has uncommitted edits; leaving the pin at $pin"
        return 0
    fi

    log "Installing Go $latest (pinned: $pin)..."
    if ! run_command mise install --yes "go@$latest"; then
        log_error "mise could not install Go $latest; leaving the pin at $pin"
        return 1
    fi
    local version
    # local: under auto, a go.mod in the working directory could switch toolchains.
    version=$(GOTOOLCHAIN=local mise exec "go@$latest" -- go version) || { log_error "Go $latest does not run"; return 1; }
    if [[ "$version" != "go version go$latest "* ]]; then
        log_error "mise's Go $latest reports '$version'; leaving the pin at $pin"
        return 1
    fi
    # Rewritten in place: the file keeps its mode, and ~/.config/mise links to it.
    local updated
    updated=$(sed -E "s/^go = \"${pin//./\\.}\"$/go = \"$latest\"/" "$file") || return
    if ! printf '%s\n' "$updated" > "$file"; then
        log_error "Could not write $file"
        git -C "$DOTFILES_DIR" checkout -- "$rel" || true
        return 1
    fi
    if ! run_command git -C "$DOTFILES_DIR" commit -S -m "mise: pin Go $latest" -- "$rel"; then
        # The file was clean before the edit, so this restores the old pin.
        git -C "$DOTFILES_DIR" checkout -- "$rel" || true
        log_error "Could not commit the Go $latest pin; left at $pin"
        return 1
    fi
    log "Pinned Go $latest; the next sync publishes it"
}

update_zinit() {
    log "=== Updating Zinit plugins ==="

    local zinit_home="${XDG_DATA_HOME:-$HOME/.local/share}/zinit/zinit.git"

    if [[ ! -d "$zinit_home" ]]; then
        log_error "Zinit not found at $zinit_home"
        return 1
    fi

    log "Updating zinit core..."
    if ! run_command git -C "$zinit_home" pull --ff-only --quiet; then
        log_error "Updating zinit itself failed; see $LOG_FILE"
        return 1
    fi

    log "Updating zinit plugins..."
    if ! run_command zsh -ic 'zinit update --all --quiet'; then
        log_error "zinit update --all failed; see $LOG_FILE"
        return 1
    fi

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
    if ! run_command "$DOTFILES_DIR/sync.sh" sync; then
        log_error "sync.sh sync failed; see $DOTFILES_DIR/logs/sync.log"
        return 1
    fi

    log "Dotfiles sync complete"
}

update_all() {
    log "======================================"
    log "Starting full system update"
    log "======================================"

    # Each stage runs whatever the others did; the run fails if any did.
    local failed=()
    update_brew || failed+=(brew)
    update_go_pin || failed+=(go)
    update_zinit || failed+=(zinit)
    sync_dotfiles || failed+=(sync)

    log "======================================"
    if [[ ${#failed[@]} -gt 0 ]]; then
        log_error "Full update finished; failed stages: ${failed[*]}"
        log "======================================"
        return 1
    fi
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
            --go)       action="go"; shift ;;
            --zinit)    action="zinit"; shift ;;
            --sync)     action="sync"; shift ;;
            --all)      action="all"; shift ;;
            --quiet)    QUIET=true; shift ;;
            --help|-h)  show_help; exit 0 ;;
            *)          log_error "Unknown option: $1"; show_help; exit 1 ;;
        esac
    done

    rotate_log "$LOG_FILE"
    case "$action" in
        brew)   update_brew ;;
        go)     update_go_pin ;;
        zinit)  update_zinit ;;
        sync)   sync_dotfiles ;;
        all)    update_all ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
