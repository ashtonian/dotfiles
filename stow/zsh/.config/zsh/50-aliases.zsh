# 50-aliases.zsh - Shell aliases

#=============================================================================
# BETTER DEFAULTS (only if command exists)
# Gated to real interactive sessions so tool/agent shells (zsh -i -c) keep
# clean builtins -- a tool calling `ls`/`cat`/`grep` gets the real command,
# not eza/bat/ggrep with different output.
# ls, du, ping and top keep their real commands even here: their replacements
# take different flags (`ls -ltr`, `du -sh`, `ping -c`), so they get their own
# names instead. gping, htop and ncdu are already their own names.
#=============================================================================
if [[ "${ZSH_REAL_SESSION:-0}" == 1 ]]; then
# Cat -> Bat
if command -v bat &>/dev/null; then
    alias cat='bat'
    alias ocat='command cat'
fi

# Listings with eza (preferred, Rust-based) or colorls as fallback. Applied here
# and again after OMZL::directories loads (its atload in 30-plugins.zsh), which
# defines its own ll and la.
_dotfiles_list_aliases() {
    [[ "${ZSH_REAL_SESSION:-0}" == 1 ]] || return 0
    if (( $+commands[eza] )); then
        alias ll='eza -l --icons --git'
        alias la='eza -la --icons --git'
        alias lt='eza --tree --level=2 --icons'
    elif (( $+commands[colorls] )); then
        alias ll='colorls -l'
        alias la='colorls -la'
        alias lt='colorls --tree=2'
    fi
}
_dotfiles_list_aliases

# Disk usage browser
if command -v ncdu &>/dev/null; then
    alias dux='ncdu --color dark -rr -x --exclude .git --exclude node_modules'
fi

# Grep -> GNU grep with color
if command -v ggrep &>/dev/null; then
    alias grep='ggrep --color=auto --exclude-dir={.bzr,CVS,.git,.hg,.svn}'
    alias ogrep='command grep'
fi
fi  # end ZSH_REAL_SESSION gate (better defaults)

#=============================================================================
# DIRECTORY NAVIGATION
#=============================================================================
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias -- -='cd -'

# Zoxide muscle-memory aliases. zoxide is initialized in 60-functions.zsh via
# `zoxide init zsh --cmd cd`, which defines `cd` (a smart superset of the
# builtin: `cd /abs/path`, `cd -`, `cd ~` all still work) and `cdi` (interactive
# picker), in real sessions only. Do NOT `alias cd=z` here -- `z` only exists
# after init runs. These aliases just keep old habits.
if [[ "${ZSH_REAL_SESSION:-0}" == 1 ]] && command -v zoxide &>/dev/null; then
    alias z='cd'     # `z foo` -> smart jump
    alias zi='cdi'   # interactive picker
    alias j='cd'     # autojump muscle memory
    alias ji='cdi'
fi

#=============================================================================
# GIT SHORTCUTS
#=============================================================================
# One definition, applied here and again after the OMZ git plugin loads (its
# atload in 30-plugins.zsh), so these win over the plugin's versions while its
# other aliases stay available.
_dotfiles_git_aliases() {
    alias g='git'
    alias gs='git status'
    alias ga='git add'
    alias gc='git commit'
    alias gp='git push'
    alias gl='git pull'
    alias gd='git diff'
    alias gco='git checkout'
    alias gb='git branch'
    alias glog='git log --oneline --graph --decorate'
}
_dotfiles_git_aliases

#=============================================================================
# COMMON TASKS
#=============================================================================
# A fresh login shell from the passwd entry, not whichever zsh is first on PATH;
# re-sourcing .zshrc stacks hooks and keeps stale state.
alias reload='exec "$SHELL" -l'
alias zshrc='${EDITOR:-vim} ~/.zshrc'
alias hosts='sudo ${EDITOR:-vim} /etc/hosts'

# DNS flush
alias fdns='sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder'

# Show/hide hidden files in Finder
alias showfiles='defaults write com.apple.finder AppleShowAllFiles YES && killall Finder'
alias hidefiles='defaults write com.apple.finder AppleShowAllFiles NO && killall Finder'

# IP addresses
alias myip='curl -s ifconfig.me'
alias localip='ipconfig getifaddr en0'

# Terraform shortcut
if command -v terraform &>/dev/null; then
    alias tf='terraform'
    alias tfcycle='tf_destroy_apply'
fi

#=============================================================================
# SAFETY (interactive only)
# In tool/agent shells with no tty, `rm -i`/`mv -i`/`cp -i` read EOF as "no"
# and SILENTLY skip the operation while exiting 0 -- a dangerous no-op. Gate to
# real sessions so scripts get the plain, predictable commands.
#=============================================================================
if [[ "${ZSH_REAL_SESSION:-0}" == 1 ]]; then
    alias rm='rm -i'
    alias mv='mv -i'
    alias cp='cp -i'
fi
