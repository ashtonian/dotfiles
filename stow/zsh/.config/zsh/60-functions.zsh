# 60-functions.zsh - Custom functions and external sources

#=============================================================================
# DOTFILES LOCATION
#=============================================================================
export DOTFILES="${DOTFILES:-$HOME/.dotfiles}"

#=============================================================================
# EXTERNAL FUNCTION FILES
#=============================================================================
# General utility functions
[[ -f "$DOTFILES/lib_sh/funcs.sh" ]] && source "$DOTFILES/lib_sh/funcs.sh"

# Claude CLI helpers (session management, code review, docs)
[[ -f "$DOTFILES/lib_sh/claude.sh" ]] && source "$DOTFILES/lib_sh/claude.sh"

# iTerm2 integrations (title management, badges, Claude helpers)
[[ -f "$DOTFILES/lib_sh/iterm2.sh" ]] && source "$DOTFILES/lib_sh/iterm2.sh"

# Colorized output helpers
[[ -f "$DOTFILES/lib_sh/echos.sh" ]] && source "$DOTFILES/lib_sh/echos.sh"

#=============================================================================
# COMPLETIONS (external tools)
#=============================================================================
# Helm completion (cached -- `helm completion zsh` is a subprocess; regenerate
# only when the helm binary is newer than the cache, not on every startup).
if command -v helm &>/dev/null; then
    () {
        local cache="${XDG_CACHE_HOME:-$HOME/.cache}/zsh/helm-completion.zsh"
        if [[ ! -s "$cache" || "$(command -v helm)" -nt "$cache" ]]; then
            mkdir -p "${cache:h}"
            helm completion zsh >| "$cache" 2>/dev/null
        fi
        source "$cache"
    }
fi

# Git extras
[[ -f "/opt/homebrew/opt/git-extras/share/git-extras/git-extras-completion.zsh" ]] && \
    source "/opt/homebrew/opt/git-extras/share/git-extras/git-extras-completion.zsh"

# Kubectl (uncomment if used)
# command -v kubectl &>/dev/null && source <(kubectl completion zsh)

#=============================================================================
# SHELL PROFILING
#=============================================================================
timezsh() {
    shell=${1-$SHELL}
    for i in $(seq 1 10); do /usr/bin/time $shell -i -c exit; done
}

#=============================================================================
# ZOXIDE (smart cd)
# Loaded synchronously (not via zinit turbo) so `cd`/`z` work in
# non-interactive shells too. --cmd cd makes `cd` a superset of the builtin:
# real paths (`cd /abs/path`, `cd -`, `cd ..`) behave normally; bare names
# fall back to frecency-ranked jumps. Provides `cd` and `cdi`.
#=============================================================================
if command -v zoxide &>/dev/null; then
    eval "$(zoxide init zsh --cmd cd)"
fi

#=============================================================================
# DIRENV (auto-load .envrc files)
#=============================================================================
if command -v direnv &>/dev/null; then
    eval "$(direnv hook zsh)"
fi

#=============================================================================
# FNM (Fast Node Manager)
#=============================================================================
if command -v fnm &>/dev/null; then
    eval "$(fnm env)"
fi
