# 50-aliases.zsh - Shell aliases

#=============================================================================
# BETTER DEFAULTS (only if command exists)
# Gated to real interactive sessions so tool/agent shells (zsh -i -c) keep
# clean builtins -- a tool calling `ls`/`cat`/`grep` gets the real command,
# not eza/bat/ggrep with different output.
#=============================================================================
if [[ "${ZSH_REAL_SESSION:-0}" == 1 ]]; then
# Ping
if command -v gping &>/dev/null; then
    alias ping='gping'
    alias oping='command ping'
fi

# Cat -> Bat
if command -v bat &>/dev/null; then
    alias cat='bat'
    alias ocat='command cat'
fi

# Top -> Htop
if command -v htop &>/dev/null; then
    alias top='htop'
    alias otop='command top'
fi

# Du -> Ncdu
if command -v ncdu &>/dev/null; then
    alias du='ncdu --color dark -rr -x --exclude .git --exclude node_modules'
    alias odu='command du'
fi

# Ls -> eza (preferred, Rust-based) or colorls as fallback
if command -v eza &>/dev/null; then
    alias ls='eza --icons'
    alias ols='command ls'
elif command -v colorls &>/dev/null; then
    alias ls='colorls'
    alias ols='command ls'
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
# picker). Do NOT `alias cd=z` here -- `z` only exists after init runs, which
# breaks `cd` in non-interactive shells. These aliases just keep old habits.
if command -v zoxide &>/dev/null; then
    alias z='cd'     # `z foo` -> smart jump
    alias zi='cdi'   # interactive picker
    alias j='cd'     # autojump muscle memory
    alias ji='cdi'
fi

#=============================================================================
# GIT SHORTCUTS
#=============================================================================
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

#=============================================================================
# COMMON TASKS
#=============================================================================
alias reload='source ~/.zshrc'
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
