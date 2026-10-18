#!/usr/bin/env bash
# Sync dotfiles and per-host app backups; install missing shared packages.
set -euo pipefail
umask 077

DOTFILES_DIR=$(cd "${DOTFILES_DIR:-$HOME/.dotfiles}" && pwd -P)
SYNC_DIR="${SYNC_DIR:-$HOME/.sync}"
LOG_DIR="$DOTFILES_DIR/logs"
LOG_FILE="$LOG_DIR/sync.log"
MAX_LOG_SIZE=1048576

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"; }
run_logged() { "$@" 2>&1 | tee -a "$LOG_FILE"; }
stable_host() { scutil --get LocalHostName 2>/dev/null || hostname -s; }

acquire_lock() {
    exec 9>>"$LOG_DIR/sync.flock" || return
    local status=0
    /usr/bin/lockf -s -t 0 9 || status=$?
    if [[ $status -ne 0 ]]; then
        exec 9>&-
        if [[ $status -eq 75 ]]; then
            log "INFO: Another sync is already running"
        else
            log "ERROR: Cannot acquire sync lock (exit $status)"
        fi
    fi
    return "$status"
}

rotate_logs() {
    if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE") -gt $MAX_LOG_SIZE ]]; then
        mv "$LOG_FILE" "$LOG_FILE.$(date +%s).old"
    fi
    local file index
    local logs=()
    for file in "$LOG_FILE".*.old; do
        [[ -f "$file" ]] && logs+=("$file")
    done
    # Epoch timestamps in generated filenames sort from oldest to newest.
    for ((index=0; index < ${#logs[@]} - 3; index++)); do
        rm -f -- "${logs[$index]}"
    done
    return 0
}

check_connectivity() {
    if ! curl -sf -m 5 https://github.com >/dev/null 2>&1; then
        log "WARN: No network connectivity, skipping sync"
        return 1
    fi
}

sync_brewfile() {
    if ! command -v brew >/dev/null; then
        log "WARN: Homebrew is not installed"
        return 1
    fi
    local file result=0
    for file in "$DOTFILES_DIR/Brewfile" "$DOTFILES_DIR/Brewfile.local"; do
        [[ -f "$file" ]] || continue
        if HOMEBREW_NO_AUTO_UPDATE=1 brew bundle check --no-upgrade --file="$file" >/dev/null 2>&1; then
            continue
        fi
        log "INFO: Installing missing packages from ${file##*/}"
        if ! run_logged env HOMEBREW_NO_AUTO_UPDATE=1 brew bundle install --no-upgrade --file="$file"; then
            log "ERROR: Package installation failed for ${file##*/}"
            result=1
        fi
    done
    return "$result"
}

run_mackup_backup() (
    if ! command -v mackup >/dev/null; then
        log "WARN: Mackup is not installed"
        return 1
    fi
    local cfg="${MACKUP_CONFIG_FILE:-$HOME/.mackup.cfg}" host_dir tmp_cfg
    host_dir="mackup/$(stable_host)"
    [[ -f "$cfg" ]] || { log "ERROR: Missing Mackup configuration"; return 1; }
    tmp_cfg=$(mktemp) || return
    trap 'rm -f -- "$tmp_cfg"' EXIT
    mkdir -p "$SYNC_DIR/$host_dir" || return
    python3 - "$cfg" "$tmp_cfg" "$SYNC_DIR" "$host_dir" <<'PY' || return
import configparser, sys
config = configparser.ConfigParser()
config.read(sys.argv[1])
if not config.has_section('storage'):
    config.add_section('storage')
config['storage'].update(engine='file_system', path=sys.argv[3], directory=sys.argv[4])
with open(sys.argv[2], 'w') as output:
    config.write(output)
PY
    log "INFO: Backing up app configs to $SYNC_DIR/$host_dir"
    run_logged mackup --config-file="$tmp_cfg" backup --force
)

repo_idle() {
    local state location conflicts
    for state in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply sequencer BISECT_LOG; do
        location=$(git rev-parse --git-path "$state") || return
        if [[ -e "$location" ]]; then
            log "ERROR: Git operation in progress ($state); leaving repository unchanged"
            return 1
        fi
    done
    conflicts=$(git ls-files -u) || return
    if [[ -n "$conflicts" ]]; then
        log "ERROR: Unresolved Git conflicts; leaving repository unchanged"
        return 1
    fi
}

signing_ready() {
    local name email key program enabled
    name=$(git config --get user.name) || name=''
    email=$(git config --get user.email) || email=''
    key=$(git config --get user.signingkey) || key=''
    program=$(git config --get gpg.program) || program='gpg'
    enabled=$(git config --get commit.gpgsign) || enabled='unset'
    if [[ -z "$name" || -z "$email" || -z "$key" ]] || ! command -v "$program" >/dev/null; then
        log "ERROR: Configure Git user.name, user.email, user.signingkey and a working gpg.program before syncing"
        return 1
    fi
    # Explicit -S is required even when commit.gpgsign is unset or false.
    [[ -n "$enabled" ]]
}

scan_dotfiles() {
    [[ "$PWD" == "$DOTFILES_DIR" ]] || return 0
    if ! command -v gitleaks >/dev/null; then
        log "ERROR: Install gitleaks before automatically publishing dotfiles"
        return 1
    fi
    if ! run_logged gitleaks git --no-banner --redact=100 --ignore-gitleaks-allow "$@" .; then
        log "ERROR: Secret scan failed; no commit or push will be attempted"
        return 1
    fi
}

integrate_remote() {
    local branch="$1" auto_resolve="$2" before after remote
    remote="refs/remotes/origin/$branch"
    git rev-parse --verify "$remote" >/dev/null || return
    before=$(git rev-parse HEAD) || return
    local options=(--no-edit --gpg-sign)
    [[ "$auto_resolve" == true ]] && options+=(-X ours)
    if ! run_logged git merge "${options[@]}" "$remote"; then
        log "ERROR: Remote integration failed; aborting merge and skipping push"
        git merge --abort 2>/dev/null || true
        return 1
    fi
    after=$(git rev-parse HEAD) || return
    if [[ "$after" != "$before" && "$after" != "$(git rev-parse "$remote")" ]]; then
        run_logged git verify-commit "$after" || return
    fi
}

github_repo() {
    local url
    url=$(git remote get-url --push origin) || return
    if [[ "$url" =~ ^(https://github\.com/|git@github\.com:|ssh://git@github\.com/)([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)$ ]]; then
        printf '%s\n' "${BASH_REMATCH[2]%.git}"
    elif [[ "$url" == *github.com* ]]; then
        log "ERROR: Cannot determine GitHub repository for signature verification" >&2
        return 1
    fi
}

verify_github_commits() {
    local repo="$1" commits="$2" sha reason attempt
    [[ -n "$repo" ]] || return 0
    while IFS= read -r sha; do
        [[ -n "$sha" ]] || continue
        reason='verification unavailable'
        for attempt in 1 2 3; do
            reason=$(gh api "repos/$repo/commits/$sha" --jq '.commit.verification | if .verified then "verified" else .reason end') || reason='verification unavailable'
            [[ "$reason" == verified ]] && break
            [[ $attempt -eq 3 ]] || sleep 2
        done
        if [[ "$reason" != verified ]]; then
            log "ERROR: GitHub commit $sha is unverified: $reason"
            if [[ "$reason" == bad_email ]]; then
                log "ERROR: Git user.email must match a verified email on the signing key"
            fi
            return 1
        fi
    done <<< "$commits"
}

sync_git_repo() (
    local repo_dir="$1" auto_resolve="${2:-false}" branch changes sha commits repo attempt
    cd "$repo_dir" || return
    git rev-parse --git-dir >/dev/null 2>&1 || { log "WARN: Not a Git repository: $repo_dir"; return 1; }
    repo_idle || return
    branch=$(git symbolic-ref --quiet --short HEAD) || { log "ERROR: Detached HEAD; skipping sync"; return 1; }
    signing_ready || return
    log "INFO: Syncing ${repo_dir##*/}"

    local has_remote=false
    if git remote get-url origin >/dev/null 2>&1; then
        has_remote=true
        if [[ "$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)" != "origin/$branch" ]]; then
            log "ERROR: Set an origin tracking branch before automatic sync"
            return 1
        fi
        run_logged git fetch origin || return
    fi
    changes=$(git status --porcelain) || return
    if [[ -n "$changes" ]]; then
        git add -A -- ':!*.local' ':!.env*' ':!*.secret*' || return
        if ! git diff --cached --quiet; then
            scan_dotfiles --staged || return
            run_logged git commit -S -m "auto: sync $(date '+%Y-%m-%d %H:%M') from $(stable_host)" || return
            sha=$(git rev-parse HEAD) || return
            run_logged git verify-commit "$sha" || return
        fi
    fi
    [[ "$has_remote" == true ]] || return 0
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
        log "ERROR: Excluded local changes remain; skipping merge and push"
        return 1
    fi
    repo=$(github_repo) || return
    if [[ -n "$repo" ]] && ! command -v gh >/dev/null; then
        log "ERROR: Install gh to verify GitHub commit signatures before publishing"
        return 1
    fi
    for attempt in 1 2 3; do
        integrate_remote "$branch" "$auto_resolve" || return
        commits=$(git rev-list "origin/$branch..HEAD") || return
        [[ -n "$commits" ]] || return 0
        while IFS= read -r sha; do run_logged git verify-commit "$sha" || return; done <<< "$commits"
        scan_dotfiles "--log-opts=origin/$branch..HEAD" || return
        if run_logged git push origin "HEAD:refs/heads/$branch"; then
            verify_github_commits "$repo" "$commits" || return
            log "INFO: Pushed verified commits for ${repo_dir##*/}"
            return 0
        fi
        [[ $attempt -eq 3 ]] && break
        sleep "$((attempt * 5))"
        run_logged git fetch origin || return
    done
    log "ERROR: Push failed after three attempts"
    return 1
)

sync_auxiliary_repos() {
    local dir result=0
    for dir in "$SYNC_DIR"/*/; do
        [[ -d "${dir}.git" || -f "${dir}.git" ]] || continue
        sync_git_repo "${dir%/}" true || result=1
    done
    return "$result"
}
sync_dotfiles() { sync_git_repo "$DOTFILES_DIR"; }

run_stow() (
    command -v stow >/dev/null || { log "ERROR: Stow is not installed"; return 1; }
    cd "$DOTFILES_DIR/stow" || return
    local package result=0
    for package in */; do
        run_logged stow -v -R -t "$HOME" "${package%/}" || result=1
    done
    return "$result"
)

main() {
    mkdir -p "$LOG_DIR" "$SYNC_DIR"
    local status=0
    acquire_lock || status=$?
    [[ $status -ne 75 ]] || return 0
    [[ $status -eq 0 ]] || return "$status"
    rotate_logs
    case "${1:-sync}" in
        check) log "INFO: Sync lock is available" ;;
        sync|all)
            check_connectivity || return 0
            sync_brewfile || status=1
            run_mackup_backup || status=1
            sync_dotfiles || status=1
            sync_auxiliary_repos || status=1
            if [[ ${1:-sync} == all ]]; then run_stow || status=1; fi
            if [[ $status -eq 0 ]]; then log "INFO: Sync complete"; else log "ERROR: Sync completed with failures"; fi
            ;;
        dotfiles) check_connectivity || return 0; sync_dotfiles || status=$? ;;
        repos) check_connectivity || return 0; sync_auxiliary_repos || status=$? ;;
        stow) run_stow || status=$? ;;
        brewfile) sync_brewfile || status=$? ;;
        mackup) run_mackup_backup || status=$? ;;
        *) printf 'Usage: %s {sync|dotfiles|repos|stow|brewfile|mackup|all|check}\n' "$0"; return 1 ;;
    esac
    return "$status"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
