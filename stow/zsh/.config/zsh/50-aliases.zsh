# 50-aliases.zsh - Shell aliases

#=============================================================================
# BETTER DEFAULTS (only if command exists)
#=============================================================================
# Ping
if command -v prettyping &>/dev/null; then
    alias ping='prettyping --nolegend'
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

# Ls -> Colorls (or exa/eza as fallback)
if command -v colorls &>/dev/null; then
    alias ls='colorls'
    alias ols='command ls'
elif command -v eza &>/dev/null; then
    alias ls='eza --icons'
    alias ols='command ls'
fi

# Grep -> GNU grep with color
if command -v ggrep &>/dev/null; then
    alias grep='ggrep --color=auto --exclude-dir={.bzr,CVS,.git,.hg,.svn}'
    alias ogrep='command grep'
fi

#=============================================================================
# DIRECTORY NAVIGATION
#=============================================================================
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias -- -='cd -'

# Zoxide (if installed, replaces cd)
if command -v zoxide &>/dev/null; then
    alias cd='z'
    alias cdi='zi'  # Interactive selection
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
# SAFETY
#=============================================================================
alias rm='rm -i'
alias mv='mv -i'
alias cp='cp -i'
