##############################################################################
# PATH
##############################################################################
export GOPATH=$HOME/go
export PATH=$GOPATH/bin:$PATH

export PATH=$HOME/bin:$PATH
export PATH=/usr/local/bin:$PATH

export PATH=/usr/local/opt/python/libexec/bin:$PATH

##############################################################################
# ZPLUG Init
##############################################################################
export ZPLUG_HOME=$(brew --prefix)/opt/zplug
source $ZPLUG_HOME/init.zsh

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
zplug 'zplug/zplug', hook-build:'zplug --self-manage'

zplug "lib/bzr.zsh", from:oh-my-zsh
zplug "lib/cli.zsh", from:oh-my-zsh
zplug "lib/clipboard.zsh", from:oh-my-zsh
zplug "lib/compfix.zsh", from:oh-my-zsh
zplug "lib/completion.zsh", from:oh-my-zsh
zplug "lib/correction.zsh", from:oh-my-zsh
zplug "lib/diagnostics.zsh", from:oh-my-zsh
zplug "lib/directories.zsh", from:oh-my-zsh
zplug "lib/functions.zsh", from:oh-my-zsh
zplug "lib/git.zsh", from:oh-my-zsh
zplug "lib/grep.zsh", from:oh-my-zsh
zplug "lib/history.zsh", from:oh-my-zsh
zplug "lib/key-bindings.zsh", from:oh-my-zsh
zplug "lib/misc.zsh", from:oh-my-zsh
zplug "lib/nvm.zsh", from:oh-my-zsh
zplug "lib/prompt_info_functions.zsh", from:oh-my-zsh
zplug "lib/spectrum.zsh", from:oh-my-zsh
zplug "lib/termsupport.zsh", from:oh-my-zsh
zplug "lib/theme-and-appearance.zsh", from:oh-my-zsh

# zplugin light "chrissicool/zsh-256color"
zplug "aperezdc/zsh-fzy"
zplug "plugins/autojump", from:oh-my-zsh
zplug "plugins/aws", from:oh-my-zsh
zplug "direnv/direnv", as:command, rename-to:direnv, use:"direnv", hook-build:"make"
zplug "djui/alias-tips"
zplug "iam4x/zsh-iterm-touchbar"
zplug "knu/zsh-manydots-magic"
zplug "lukechilds/zsh-better-npm-completion", defer:3
zplug "lukechilds/zsh-nvm"
zplug "mafredri/zsh-async", from:"github", use:"async.zsh"
zplug "MichaelAquilina/zsh-you-should-use"
zplug "plugins/copyfile",  from:oh-my-zsh, defer:2
zplug "plugins/dnf",   from:oh-my-zsh
zplug "plugins/docker-compose",   from:oh-my-zsh
zplug "plugins/docker",   from:oh-my-zsh
zplug "plugins/encode64",   from:oh-my-zsh, defer:2
zplug "plugins/extract",   from:oh-my-zsh, defer:2
zplug "plugins/gem",   from:oh-my-zsh
zplug "plugins/git-auto-fetch",   from:oh-my-zsh, defer:3
zplug "plugins/git-extras", from:oh-my-zsh, defer:3
zplug "plugins/git-prompt",   from:oh-my-zsh, defer:3
zplug "plugins/git",   from:oh-my-zsh, defer:3
zplug "plugins/gitfast", from:oh-my-zsh, defer:3
zplug "plugins/golang",   from:oh-my-zsh, defer:3
zplug "plugins/gpg-agent",   from:oh-my-zsh
zplug "plugins/helm", from:oh-my-zsh
zplug "plugins/history",   from:oh-my-zsh, defer:1
zplug "plugins/iterm2",   from:oh-my-zsh
zplug "plugins/kubectl",   from:oh-my-zsh, defer:3
zplug "plugins/node",   from:oh-my-zsh
zplug "plugins/npm",   from:oh-my-zsh
zplug "plugins/osx",   from:oh-my-zsh, defer:2
zplug "plugins/rake",   from:oh-my-zsh
zplug "plugins/rsync",   from:oh-my-zsh
zplug "plugins/ruby",   from:oh-my-zsh
zplug "plugins/shrink-path",   from:oh-my-zsh
zplug "plugins/ssh-agent",   from:oh-my-zsh
zplug "plugins/systemd",   from:oh-my-zsh
zplug "plugins/terraform",   from:oh-my-zsh
zplug "plugins/thefuck",   from:oh-my-zsh
zplug "plugins/tmux",   from:oh-my-zsh, defer:3
zplug "plugins/vagrant",   from:oh-my-zsh
zplug "plugins/vscode",   from:oh-my-zsh, defer:2
zplug "plugins/web-search", from:oh-my-zsh, defer:2
zplug "plugins/z",   from:oh-my-zsh
zplug "plugins/zsh_reload",   from:oh-my-zsh
zplug "simonwhitaker/gibo", use:'shell-completions/gibo-completion.zsh', as:plugin #verify
zplug "tysonwolker/iterm-tab-colors"
zplug "zdharma/zsh-diff-so-fancy", as:command, use:"bin/"
zplug "plugins/zsh-interactive-cd", from:oh-my-zsh
zplug "zsh-users/zsh-apple-touchbar"
zplug "zsh-users/zsh-autosuggestions", defer:3
zplug "zsh-users/zsh-completions", use:src
zplug "zsh-users/zsh-history-substring-search", defer:3
zplug "zsh-users/zsh-syntax-highlighting", defer:2
zplug "aperezdc/zsh-fzy"

# TODO: migrate to zinit
# TODO: https://github.com/xxh/xxh
# TODO: ZSH_THEME="robbyrussell"

# Install plugins if there are plugins that have not been installed
if ! zplug check --verbose; then
    printf "Install? [y/N]: "
    if read -q; then
        echo; zplug install
    fi
fi

# Then, source plugins and add commands to $PATH
zplug load