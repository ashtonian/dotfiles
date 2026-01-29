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

# Colorized output helpers
[[ -f "$DOTFILES/lib_sh/echos.sh" ]] && source "$DOTFILES/lib_sh/echos.sh"

#=============================================================================
# COMPLETIONS (external tools)
#=============================================================================
# Helm
if command -v helm &>/dev/null; then
    source <(helm completion zsh) 2>/dev/null
fi

# Git extras
[[ -f "/opt/homebrew/opt/git-extras/share/git-extras/git-extras-completion.zsh" ]] && \
    source "/opt/homebrew/opt/git-extras/share/git-extras/git-extras-completion.zsh"

# Kubectl (uncomment if used)
# command -v kubectl &>/dev/null && source <(kubectl completion zsh)

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
