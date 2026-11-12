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

# OpenCode helpers (oc / ocweb: attach to the local OpenCode server)
[[ -f "$DOTFILES/lib_sh/opencode.sh" ]] && source "$DOTFILES/lib_sh/opencode.sh"

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
# ZOXIDE (smart cd, real terminal sessions only)
# --cmd cd makes `cd` a superset of the builtin: real paths (`cd /abs/path`,
# `cd -`, `cd ..`) behave normally; bare names fall back to frecency-ranked
# jumps. Provides `cd` and `cdi`. Tool and agent shells keep the builtin: a
# frecency jump there turns `cd build && rm -rf *` into a command in another
# tree.
#=============================================================================
if [[ "${ZSH_REAL_SESSION:-0}" == 1 ]]; then
    _dotfiles_cached_eval zoxide-init -e _ZO_ECHO -e _ZO_RESOLVE_SYMLINKS zoxide init zsh --cmd cd
fi

#=============================================================================
# DIRENV (auto-load .envrc files)
#=============================================================================
_dotfiles_cached_eval direnv-hook direnv hook zsh

#=============================================================================
# MISE (tool versions per directory: Go, Node, Python and others)
#=============================================================================
# Real sessions update PATH at each prompt and directory change. Every other
# shell, agents and LaunchAgents included, gets mise's shims from env.sh. Not
# cached: the activation script carries this shell's PATH as literal values.
if [[ "${ZSH_REAL_SESSION:-0}" == 1 ]] && (( $+commands[mise] )); then
    eval "$(mise activate zsh)"
fi

#=============================================================================
# GITSTEAD (`gitstead cd <query>` + completion)
#=============================================================================
if command -v gitstead &>/dev/null; then
    eval "$(gitstead shell-init zsh)"
fi
