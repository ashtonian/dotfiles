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
zinit ice wait"0" lucid from"gh-r" as"program"
zinit light junegunn/fzf

# Alias tips (shows alias when you type full command)
zinit ice wait"1" lucid
zinit light djui/alias-tips

#=============================================================================
# OMZ LIBRARIES (cherry-picked essentials)
#=============================================================================
zinit ice wait"0" lucid
zinit snippet OMZL::clipboard.zsh

zinit ice wait"0" lucid
zinit snippet OMZL::completion.zsh

zinit ice wait"0" lucid
zinit snippet OMZL::directories.zsh

zinit ice wait"0" lucid
zinit snippet OMZL::git.zsh

zinit ice wait"0" lucid
zinit snippet OMZL::history.zsh

zinit ice wait"0" lucid
zinit snippet OMZL::key-bindings.zsh

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
# Wakatime
zinit ice wait"2" lucid
zinit light sobolevn/wakatime-zsh-plugin

# iTerm2 Shell Integration (full version, not just OMZ plugin)
# Provides: imgcat, imgls, it2api, it2setcolor, it2setkeylabel, etc.
# Also enables: shell integration marks, command history with timestamps,
# automatic profile switching, current dir reporting, and more
zinit ice wait"0" lucid \
    id-as"iterm2-shell-integration" \
    atclone"curl -fsSL https://iterm2.com/shell_integration/zsh -o iterm2_shell_integration.zsh" \
    atpull"%atclone" \
    src"iterm2_shell_integration.zsh"
zinit light zdharma-continuum/null

# Git-it-on (open git repo in browser)
zinit ice wait"2" lucid
zinit light peterhurford/git-it-on.zsh

#=============================================================================
# COMPLETIONS (loaded last, after compinit)
#=============================================================================
zinit ice wait"2" lucid blockf atpull"zinit creinstall -q ."
zinit light zsh-users/zsh-completions

# Initialize completion system
autoload -Uz compinit
if [[ -n ${ZDOTDIR}/.zcompdump(#qN.mh+24) ]]; then
    compinit
else
    compinit -C
fi

# Replay completions
zinit cdreplay -q
