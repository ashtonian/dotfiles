#!/usr/bin/env bash
# Sync dotfiles and auxiliary repositories; install missing shared packages.
set -euo pipefail
umask 077

DOTFILES_DIR=$(cd "${DOTFILES_DIR:-$HOME/.dotfiles}" && pwd -P)
SYNC_DIR="${SYNC_DIR:-$HOME/.sync}"
LOG_DIR="$DOTFILES_DIR/logs"
LOG_FILE="$LOG_DIR/sync.log"
MAX_LOG_SIZE=1048576
# A repository with a tracked change newer than this is being edited; sync
# leaves it for a later run instead of committing half-finished work.
SYNC_QUIET_MINUTES="${SYNC_QUIET_MINUTES:-30}"
# Machine-local files found inside stow packages are held here while their
# package is relinked. Same volume as $HOME, so moves are renames.
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles"
# The feature engine (cmd/dotfiles): this machine's manifest, the binary sync
# builds from the checkout, and where apply writes the generated Brewfile.
MACHINE_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/machine.toml"
DOTFILES_BIN="${DOTFILES_BIN:-$HOME/.local/bin/dotfiles}"
GENERATED_DIR="$HOME/.config/dotfiles/generated"

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

# A checkout with features/ is installed by the engine; one without is the
# older stow layout.
uses_engine() { [[ -d "$DOTFILES_DIR/features" ]]; }

sync_brewfile() {
    if ! command -v brew >/dev/null; then
        log "WARN: Homebrew is not installed"
        return 1
    fi
    local file result=0 shared="$DOTFILES_DIR/Brewfile"
    uses_engine && shared="$GENERATED_DIR/Brewfile"
    for file in "$shared" "$DOTFILES_DIR/Brewfile.local"; do
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

# Succeeds, and names the reason, when someone is working in the repository.
repo_busy() {
    local lock file
    lock=$(git rev-parse --git-path index.lock) || return 1
    if [[ -e "$lock" ]]; then
        log "INFO: ${PWD##*/} has a Git index lock; leaving it for the next sync"
        return 0
    fi
    while IFS= read -r -d '' file; do
        [[ -e "$file" ]] || continue
        if [[ -n "$(find "$file" -prune -mmin "-$SYNC_QUIET_MINUTES" 2>/dev/null)" ]]; then
            log "INFO: ${PWD##*/} changed in the last $SYNC_QUIET_MINUTES minutes ($file); leaving it for the next sync"
            return 0
        fi
    done < <(git diff --name-only -z HEAD --)
    return 1
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

# upstream_ready REF: merging REF must leave this machine installable. When REF
# uses the feature engine, this machine needs its manifest, and REF's own
# engine has to build here and plan that manifest, before the merge. A merge
# that brought a layout the engine cannot install would leave every link the
# current layout made pointing at moved or changed files, with nothing to
# replace them: no shell config, no git identity for the next sync.
upstream_ready() {
    local ref="$1" profiles tree status=0
    git cat-file -e "$ref:features" 2>/dev/null || return 0
    [[ -n "$(git rev-list --max-count=1 "HEAD..$ref")" ]] || return 0
    if [[ ! -f "$MACHINE_FILE" ]]; then
        profiles=$(git ls-tree --name-only "$ref:profiles" 2>/dev/null | sed 's/\.toml$//' | tr '\n' ' ')
        log "ERROR: $ref installs machine features and this machine has no $MACHINE_FILE; skipping merge and push until it lists this machine's profiles, such as: profiles = [\"base\", \"dev\"] (available: ${profiles% })"
        return 1
    fi
    if ! command -v go >/dev/null; then
        log "ERROR: $ref installs machine features and Go is not installed to build its engine; skipping merge and push until Go is installed (brew install go)"
        return 1
    fi
    tree=$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-upstream.XXXXXX") || return
    if git archive --format=tar "$ref" | tar -x -f - -C "$tree" &&
        (cd "$tree" && run_logged env GOTOOLCHAIN=local go build -trimpath -o "$tree/.dotfiles-check" ./cmd/dotfiles) &&
        run_logged "$tree/.dotfiles-check" check --repo "$tree" --machine "$MACHINE_FILE"; then
        status=0
    else
        log "ERROR: $ref's engine does not build with this machine's Go or cannot plan $MACHINE_FILE (see above); skipping merge and push"
        status=1
    fi
    rm -rf -- "$tree"
    return "$status"
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
    local repo_dir="$1" auto_resolve="${2:-false}" branch changes untracked sha commits repo attempt
    cd "$repo_dir" || return
    git rev-parse --git-dir >/dev/null 2>&1 || { log "WARN: Not a Git repository: $repo_dir"; return 1; }
    repo_idle || return
    if repo_busy; then return 0; fi
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
    changes=$(git status --porcelain --untracked-files=no) || return
    untracked=$(git ls-files --others --exclude-standard | wc -l | tr -d ' ') || return
    if [[ "$untracked" -gt 0 ]]; then
        log "INFO: ${repo_dir##*/} has $untracked untracked file(s); sync never publishes new files, so commit them by hand"
    fi
    if [[ -n "$changes" ]]; then
        # Tracked files only: a file a tool drops into the tree is never published.
        git add -u -- . ':(exclude,glob)**/*.local' ':(exclude,glob)**/.env*' ':(exclude,glob)**/*.secret*' || return
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
    if [[ "$repo_dir" == "$DOTFILES_DIR" ]] && ! upstream_ready "origin/$branch"; then return 1; fi
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

# build_engine: rebuild the binary when the checkout's engine sources are newer
# than it, which a pull that changes them makes them. GOTOOLCHAIN=local: a
# background job never downloads a Go toolchain.
build_engine() {
    local path stale="" sources=()
    for path in go.mod go.sum cmd internal; do
        [[ -e "$DOTFILES_DIR/$path" ]] && sources+=("$DOTFILES_DIR/$path")
    done
    if [[ -x "$DOTFILES_BIN" ]]; then
        [[ ${#sources[@]} -gt 0 ]] || return 0
        stale=$(find "${sources[@]}" -newer "$DOTFILES_BIN" -print -quit) || return
        [[ -n "$stale" ]] || return 0
    fi
    if ! command -v go >/dev/null; then
        log "ERROR: Go is not installed; cannot build $DOTFILES_BIN"
        return 1
    fi
    log "INFO: Building $DOTFILES_BIN"
    mkdir -p "${DOTFILES_BIN%/*}" || return
    if ! (cd "$DOTFILES_DIR" && run_logged env GOTOOLCHAIN=local go build -trimpath -o "$DOTFILES_BIN.tmp" ./cmd/dotfiles); then
        rm -f "$DOTFILES_BIN.tmp"
        log "ERROR: Building $DOTFILES_BIN failed"
        return 1
    fi
    mv -f "$DOTFILES_BIN.tmp" "$DOTFILES_BIN"
}

# apply_features: converge this machine on its features. The engine's own
# lock serializes it with a manual `dotfiles apply`.
apply_features() {
    uses_engine || return 0
    if [[ ! -f "$MACHINE_FILE" ]]; then
        log "ERROR: No machine manifest at $MACHINE_FILE; run: $DOTFILES_BIN init --profiles <names>"
        return 1
    fi
    build_engine || return
    local status=0
    run_logged "$DOTFILES_BIN" apply --repo "$DOTFILES_DIR" || status=$?
    case $status in
        0) return 0 ;;
        1) log "WARN: dotfiles apply left problems to resolve; see above, or run: $DOTFILES_BIN doctor" ;;
        *) log "ERROR: dotfiles apply failed (exit $status)" ;;
    esac
    return 1
}

# Directories stow must never turn into links into the repository, created
# private before any package is linked.
HOME_DIRS=(.claude .config .local/bin .local/share .ssh)

ensure_home_dirs() {
    local dir
    for dir in "${HOME_DIRS[@]}"; do
        # A link here is a folded package directory; relinking its package
        # replaces it with a real directory.
        [[ -L "$HOME/$dir" ]] && continue
        mkdir -p "$HOME/$dir" || return
    done
    for dir in .claude .ssh; do
        [[ -L "$HOME/$dir" ]] || chmod 700 "$HOME/$dir" || return
    done
}

# Ignored files inside a package were written by tools through a folded
# directory link (gh's hosts.yml, opencode's node_modules). They belong in
# $HOME, not the repository, and must not be linked back in.
hold_ignored() {
    local package="$1" hold="$2" path manifest="$2/$1.held"
    mkdir -p "$hold" || return
    : > "$manifest" || return
    while IFS= read -r -d '' path; do
        path=${path%/}
        mkdir -p "$hold/$(dirname "$path")" || return
        mv "$DOTFILES_DIR/$path" "$hold/$path" || return
        printf '%s\0' "$path" >> "$manifest" || return
    done < <(git -C "$DOTFILES_DIR" ls-files -z --others --ignored --exclude-standard --directory -- "stow/$package")
}

# Puts held files back into the package after a failed relink.
return_held() {
    local package="$1" hold="$2" path manifest="$2/$1.held"
    [[ -f "$manifest" ]] || return 0
    while IFS= read -r -d '' path; do
        mkdir -p "$DOTFILES_DIR/$(dirname "$path")" || return
        mv "$hold/$path" "$DOTFILES_DIR/$path" || return
    done < "$manifest"
    rm -f -- "$manifest"
}

# Moves held files to their place in $HOME. A real file already there is
# kept, and the held copy stays in the hold directory for the owner.
place_held() {
    local package="$1" hold="$2" path rel dest manifest="$2/$1.held" result=0
    [[ -f "$manifest" ]] || return 0
    while IFS= read -r -d '' path; do
        rel=${path#"stow/$package/"}
        dest="$HOME/$rel"
        # A link stow made to this file before it was held now dangles.
        if [[ -L "$dest" && "$(readlink "$dest")" == *"/stow/$package/$rel" ]]; then
            rm -f -- "$dest" || return
        fi
        if [[ -e "$dest" || -L "$dest" ]]; then
            log "ERROR: $dest already exists; the machine-local copy from the repository is in $hold/$path"
            result=1
            continue
        fi
        mkdir -p "$(dirname "$dest")" || return
        mv "$hold/$path" "$dest" || return
        log "INFO: Moved machine-local $path out of the repository to $dest"
    done < "$manifest"
    [[ $result -ne 0 ]] || rm -f -- "$manifest"
    return "$result"
}

# One package at a time: hold its ignored files, relink it without folding
# (stow changes nothing if it finds a conflict), then move the held files home.
stow_package() {
    local package="$1" hold="$2"
    hold_ignored "$package" "$hold" || { return_held "$package" "$hold"; return 1; }
    if ! run_logged stow --no-folding -R -v -t "$HOME" "$package"; then
        log "ERROR: Stow left $package unchanged; resolve the conflict above and run sync.sh stow"
        return_held "$package" "$hold" || log "ERROR: Machine-local files for $package remain in $hold"
        return 1
    fi
    place_held "$package" "$hold"
}

report_untracked() {
    local files
    files=$(git -C "$DOTFILES_DIR" ls-files --others --exclude-standard -- stow) || return 0
    [[ -n "$files" ]] || return 0
    log "WARN: Untracked files in stow packages are linked but never published; commit or remove them:"
    printf '%s\n' "$files" | sed 's/^/    /' | tee -a "$LOG_FILE"
}

run_stow() (
    command -v stow >/dev/null || { log "ERROR: Stow is not installed"; return 1; }
    cd "$DOTFILES_DIR/stow" || return
    ensure_home_dirs || return
    local package result=0 hold
    hold="$STATE_DIR/stow-hold/$(date +%Y%m%dT%H%M%S)-$$"
    for package in */; do
        stow_package "${package%/}" "$hold" || result=1
    done
    find "$hold" -depth -type d -empty -delete 2>/dev/null || true
    report_untracked
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
            # Apply right after the merge: a pull that moves tracked files
            # leaves links to their old paths until it runs. The Brewfile it
            # generates is installed next.
            sync_dotfiles || status=1
            apply_features || status=1
            sync_brewfile || status=1
            sync_auxiliary_repos || status=1
            if [[ ${1:-sync} == all ]] && ! uses_engine; then run_stow || status=1; fi
            if [[ $status -eq 0 ]]; then log "INFO: Sync complete"; else log "ERROR: Sync completed with failures"; fi
            ;;
        dotfiles) check_connectivity || return 0; sync_dotfiles || status=$? ;;
        repos) check_connectivity || return 0; sync_auxiliary_repos || status=$? ;;
        apply) apply_features || status=$? ;;
        stow) if uses_engine; then apply_features || status=$?; else run_stow || status=$?; fi ;;
        brewfile) sync_brewfile || status=$? ;;
        *) printf 'Usage: %s {sync|dotfiles|repos|apply|stow|brewfile|all|check}\n' "$0"; return 1 ;;
    esac
    return "$status"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
