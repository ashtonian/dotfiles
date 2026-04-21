# 30-plugins.zsh - Zinit plugin configuration
# Uses turbo mode for async loading where possible

#=============================================================================
# THEME - Dracula (loaded first, synchronously)
#=============================================================================
zinit light dracula/zsh

#=============================================================================
# ESSENTIAL PLUGINS (loaded immediately)
#=============================================================================
# Syntax highlighting (must load before zsh-history-substring-search)
zinit light zsh-users/zsh-syntax-highlighting

# Autosuggestions
ZSH_AUTOSUGGEST_STRATEGY=(history completion)
ZSH_AUTOSUGGEST_USE_ASYNC=true
zinit light zsh-users/zsh-autosuggestions

# Completions
zinit light zsh-users/zsh-completions

#=============================================================================
# COMPINIT (must run before turbo plugins that call compdef)
#=============================================================================
autoload -Uz compinit && compinit
zinit cdreplay -q

#=============================================================================
# TURBO MODE PLUGINS (loaded async after prompt)
# wait"0" = load immediately after prompt
# wait"1" = load 1 second after prompt
#=============================================================================

# Fast directory jumping (replaces autojump - much faster)
zinit ice wait"0" lucid from"gh-r" as"program" pick"zoxide" \
    atclone"./zoxide init zsh > init.zsh" atpull"%atclone" src"init.zsh"
zinit light ajeetdsouza/zoxide

# Autopair brackets/quotes
zinit ice wait"0" lucid
zinit light hlissner/zsh-autopair

# Better directory colors
zinit ice wait"0" lucid
zinit light trapd00r/LS_COLORS

# Diff-so-fancy for git
zinit ice wait"1" lucid as"program" pick"bin/git-dsf"
zinit light z-shell/zsh-diff-so-fancy

# FZF (fuzzy finder)
zinit ice wait"0" lucid from"gh-r" as"program" \
    atload'eval "$(fzf --zsh)"'
zinit light junegunn/fzf

# Alias reminder (shows alias when you type full command)
zinit ice wait"1" lucid
zinit light MichaelAquilina/zsh-you-should-use

#=============================================================================
# PLUGIN CONFIGURATION
#=============================================================================
# SSH agent forwarding
zstyle :omz:plugins:ssh-agent agent-forwarding on

# Custom web search engines
ZSH_WEB_SEARCH_ENGINES=(reddit "https://old.reddit.com/search/?q=")

#=============================================================================
# DRACULA SYNTAX HIGHLIGHTING THEME
#=============================================================================
zinit ice wait"0" lucid
zinit light dracula/zsh-syntax-highlighting

#=============================================================================
# OMZ LIBRARIES (cherry-picked essentials)
#=============================================================================
zinit ice wait"0" lucid
zinit snippet OMZL::clipboard.zsh

# NOTE: OMZL::completion.zsh removed — compinit called explicitly above

zinit ice wait"0" lucid
zinit snippet OMZL::directories.zsh

# NOTE: OMZL::git.zsh removed - OMZP::git loads it internally
# NOTE: OMZL::history.zsh removed - custom settings in 20-history.zsh
# NOTE: OMZL::key-bindings.zsh removed - custom bindings in 40-keybindings.zsh

#=============================================================================
# OMZ PLUGINS (turbo loaded)
#=============================================================================
# Git (using regular git plugin - gitfast requires SVN checkout for multi-file support)
zinit ice wait"0" lucid
zinit snippet OMZP::git

zinit ice wait"0" lucid
zinit snippet OMZP::git-auto-fetch

# Colored man pages
zinit ice wait"1" lucid
zinit snippet OMZP::colored-man-pages

# Extract any archive
zinit ice wait"1" lucid
zinit snippet OMZP::extract

# Encode/decode base64
zinit ice wait"1" lucid
zinit snippet OMZP::encode64

# Copy file contents to clipboard
zinit ice wait"1" lucid
zinit snippet OMZP::copyfile

# macOS utilities
# NOTE: Requires `brew install subversion` for full functionality (music/spotify scripts)
# Uncomment once svn is installed:
# zinit ice wait"1" lucid svn
# zinit snippet OMZP::macos

# Docker completions (from docker CLI directly if available, fallback to bundled)
zinit ice wait"1" lucid as"completion" \
    id-as"docker-completion" \
    has"docker" \
    atclone"docker completion zsh > _docker" \
    atpull"%atclone"
zinit light zdharma-continuum/null

zinit ice wait"1" lucid
zinit snippet OMZP::docker-compose

# Terraform
zinit ice wait"1" lucid
zinit snippet OMZP::terraform

# Golang
zinit ice wait"1" lucid
zinit snippet OMZP::golang

# Node/npm
zinit ice wait"1" lucid
zinit snippet OMZP::node

zinit ice wait"1" lucid
zinit snippet OMZP::npm

# Ruby/Rake
zinit ice wait"2" lucid
zinit snippet OMZP::ruby

zinit ice wait"2" lucid
zinit snippet OMZP::rake

# GPG agent
zinit ice wait"1" lucid
zinit snippet OMZP::gpg-agent

# SSH agent
zinit ice wait"1" lucid
zinit snippet OMZP::ssh-agent

# Rsync
zinit ice wait"2" lucid
zinit snippet OMZP::rsync

# Tmux
zinit ice wait"2" lucid
zinit snippet OMZP::tmux

# VSCode
zinit ice wait"2" lucid
zinit snippet OMZP::vscode

# Web search
zinit ice wait"2" lucid
zinit snippet OMZP::web-search

#=============================================================================
# CUSTOM PLUGINS
#=============================================================================
# NOTE: wakatime-zsh-plugin removed - wakatime-cli handles tracking natively
# NOTE: git-it-on.zsh removed - use `gh repo view --web` instead

# iTerm2 integration (simple OMZ plugin - stable with Dracula theme)
# For full shell integration, install via: iTerm2 > Install Shell Integration
zinit ice wait"1" lucid
zinit snippet OMZP::iterm2

#=============================================================================
# COMPLETIONS (loaded last, after compinit)
#=============================================================================
zinit ice wait"2" lucid blockf atpull"zinit creinstall -q ."
zinit light zsh-users/zsh-completions
