##############################################################################
# PATH
##############################################################################
export GOPATH=$HOME/go
export PATH=$GOPATH/bin:$PATH

export PATH=$HOME/bin:$PATH
export PATH=/usr/local/bin:$PATH

export PATH=/usr/local/opt/python/libexec/bin:$PATH

##############################################################################
##############################################################################

##############################################################################
# Plugins - History Configuration
##############################################################################
ZSH_HISTORY_FILE_NAME=".zsh_history"
ZSH_HISTORY_FILE="${HOME}/${ZSH_HISTORY_FILE_NAME}"
ZSH_HISTORY_PROJ="${HOME}/.zsh_history_proj"
ZSH_HISTORY_FILE_ENC_NAME="zsh_history"
ZSH_HISTORY_FILE_ENC="${ZSH_HISTORY_PROJ}/${ZSH_HISTORY_FILE_ENC_NAME}"
GIT_COMMIT_MSG="latest $(date)"

export HISTFILE=~/.zsh_history # Where it gets saved
export HISTSIZE=10000
export SAVEHIST=10000
export HISTCONTROL=ignoredups
setopt append_history # Don't overwrite, append!
setopt INC_APPEND_HISTORY # Write after each command
setopt hist_expire_dups_first # Expire duplicate entries first when trimming history.
setopt hist_fcntl_lock # use OS file locking
setopt hist_ignore_all_dups # Delete old recorded entry if new entry is a duplicate.
setopt hist_lex_words # better word splitting, but more CPU heavy
setopt hist_reduce_blanks # Remove superfluous blanks before recording entry.
setopt hist_save_no_dups # Don't write duplicate entries in the history file.
setopt share_history # share history between multiple shells
# setopt HIST_IGNORE_SPACE # Don't record an entry starting with a space.


##############################################################################
# Plugins - NVM
##############################################################################
export NVM_LAZY_LOAD=true
export NVM_COMPLETION=true
export NVM_AUTO_USE=true

##############################################################################
# Plugins - Alias Tips
##############################################################################
export ZSH_PLUGINS_ALIAS_TIPS_TEXT="Alias tip: "

##############################################################################
# Plugins - ssh-agent
##############################################################################
zstyle :omz:plugins:ssh-agent agent-forwarding on #identities id_rsa id_rsa2 id_github

##############################################################################
# Plugins - Auto Suggest
##############################################################################
export ZSH_AUTOSUGGEST_USE_ASYNC=true
export ZSH_AUTOSUGGEST_STRATEGY=(history completion)

##############################################################################
# Plugins - Web Search
##############################################################################
ZSH_WEB_SEARCH_ENGINES=(reddit "https://old.reddit.com/search/?q=")

##############################################################################
# Plugins - Install
##############################################################################
# // self manage zinit
# // zinit lib


### Added by Zinit's installer
if [[ ! -f $HOME/.zinit/bin/zinit.zsh ]]; then
    print -P "%F{33}▓▒░ %F{220}Installing %F{33}DHARMA%F{220} Initiative Plugin Manager (%F{33}zdharma/zinit%F{220})…%f"
    command mkdir -p "$HOME/.zinit" && command chmod g-rwX "$HOME/.zinit"
    command git clone https://github.com/zdharma/zinit "$HOME/.zinit/bin" && \
        print -P "%F{33}▓▒░ %F{34}Installation successful.%f%b" || \
        print -P "%F{160}▓▒░ The clone has failed.%f%b"
fi

source "$HOME/.zinit/bin/zinit.zsh"
autoload -Uz _zinit
(( ${+_comps} )) && _comps[zinit]=_zinit

# Load a few important annexes, without Turbo
# (this is currently required for annexes)
zinit light-mode for \
    zinit-zsh/z-a-rust \
    zinit-zsh/z-a-as-monitor \
    zinit-zsh/z-a-patch-dl \
    zinit-zsh/z-a-bin-gem-node

### End of Zinit's installer chunk

zinit snippet OMZL::bzr.zsh
zinit snippet OMZL::cli.zsh
zinit snippet OMZL::clipboard.zsh
zinit snippet OMZL::compfix.zsh
zinit snippet OMZL::completion.zsh
zinit snippet OMZL::correction.zsh
zinit snippet OMZL::diagnostics.zsh
zinit snippet OMZL::directories.zsh
zinit snippet OMZL::functions.zsh
zinit snippet OMZL::git.zsh
zinit snippet OMZL::grep.zsh
zinit snippet OMZL::history.zsh
zinit snippet OMZL::key-bindings.zsh
zinit snippet OMZL::misc.zsh
zinit snippet OMZL::nvm.zsh
zinit snippet OMZL::prompt_info_functions.zsh
zinit snippet OMZL::spectrum.zsh
zinit snippet OMZL::termsupport.zsh
zinit snippet OMZL::theme-and-appearance.zsh
zinit autoload'#manydots-magic' for knu/zsh-manydots-magic

zinit light zsh-users/zsh-completions
zinit load tysonwolker/iterm-tab-colors
zinit snippet OMZP::docker
zinit snippet OMZP::docker-compose
zinit light zdharma/zsh-diff-so-fancy
zinit light zsh-users/zsh-history-substring-search
zinit load aperezdc/zsh-fzy
zinit load iam4x/zsh-iterm-touchbar
zinit load MichaelAquilina/zsh-you-should-use
zinit load sei40kr/zsh-fast-alias-tips
zinit load simonwhitaker/gibo
zinit load zsh-users/zsh-apple-touchbar
zinit load zsh-users/zsh-history-substring-search
zinit snippet OMZP::autojump
zinit snippet OMZP::aws
zinit snippet OMZP::copyfile
zinit snippet OMZP::dnf
zinit snippet OMZP::encode64
zinit snippet OMZP::extract
zinit snippet OMZP::gem
zinit snippet OMZP::git
zinit snippet OMZP::git-auto-fetch
zinit snippet OMZP::git-extras
zinit snippet OMZP::git-prompt
zinit snippet OMZP::gitfast
zinit snippet OMZP::golang
zinit snippet OMZP::gpg-agent
zinit snippet OMZP::helm
zinit snippet OMZP::history
zinit snippet OMZP::iterm2
zinit snippet OMZP::kubectl
zinit snippet OMZP::node
zinit snippet OMZP::npm
zinit snippet OMZP::osx
zinit snippet OMZP::rake
zinit snippet OMZP::rsync
zinit snippet OMZP::ruby
zinit snippet OMZP::shrink-path
zinit snippet OMZP::ssh-agent
zinit snippet OMZP::systemd
zinit snippet OMZP::terraform
zinit snippet OMZP::thefuck
zinit snippet OMZP::tmux
zinit snippet OMZP::vagrant
zinit snippet OMZP::vscode
zinit snippet OMZP::web-search
zinit snippet OMZP::z
zinit snippet OMZP::zsh_reload
zinit snippet OMZP::zsh-interactive-cd

zinit ice wait"1" lucid
zinit load lukechilds/zsh-better-npm-completion
zinit ice wait"1" lucid
zinit load lukechilds/zsh-nvm
zinit ice wait"0a" lucid atload"_zsh_autosuggest_start"
zinit light zsh-users/zsh-autosuggestions
zinit ice from"gh-r" as"program" mv"direnv* -> direnv" for
zinit load direnv/
zinit ice from'gh-r' as'program'
zinit load sei40kr/fast-alias-tips-bin
zinit ice wait"2" lucid as"program" pick"bin/git-dsf"
zinit load zdharma/zsh-diff-so-fancy

# TODO: migrate to zinit
# TODO: https://github.com/xxh/xxh
# TODO: ZSH_THEME="robbyrussell"
