##############################################################################
# THEME - instant Prompt 
##############################################################################
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

##############################################################################
# PATH
##############################################################################
export GOPATH=$HOME/go
export PATH=$GOPATH/bin:$PATH

export PATH=$HOME/bin:$PATH
export PATH=/usr/local/bin:$PATH

export PATH=/usr/local/opt/python/libexec/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH="/Users/ashtonian/.oh-my-zsh"

##############################################################################
# THEME & OMZ Global
##############################################################################
# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="powerlevel10k/powerlevel10k"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment the following line to disable bi-weekly auto-update checks.
# DISABLE_AUTO_UPDATE="true"

# Uncomment the following line to automatically update without prompting.
# DISABLE_UPDATE_PROMPT="true"

# Uncomment the following line to change how often to auto-update (in days).
# export UPDATE_ZSH_DAYS=13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# Caution: this setting can cause issues with multiline prompts (zsh 5.7.1 and newer seem to work)
# See https://github.com/ohmyzsh/ohmyzsh/issues/5765
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

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

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.

plugins=(
    autojump #SLOW!
    # aws #SLOW! use only when needed
    copyfile
    dnf
    docker
    docker-compose
    encode64
    extract
    gem
    git #SLOW!
    git-auto-fetch
    git-extras
    git-prompt
    gitfast
    golang
    gpg-agent
    # helm #SLOW! use only when needed
    history
    iterm2
    kubectl
    node
    npm
    osx
    rake
    rsync
    ruby
    shrink-path
    ssh-agent
    systemd
    terraform
    # thefuck #-> use zsh-thefuck instead for speed
    tmux
    vagrant
    vscode
    web-search
    z
    zsh_reload
    zsh-interactive-cd
    ###### Custom ####################################
    autoupdate
    # iterm-tab-colors #see pr https://github.com/tysonwolker/iterm-tab-colors/pull/14 
    zsh-256color
    zsh-autosuggestions
    zsh-completions
    Zsh-Diff-So-Fancy
    # zsh-fast-alias-tips #see PR https://github.com/sei40kr/zsh-fast-alias-tips/pull/25
    zsh-fzy
    zsh-syntax-highlighting
    zsh-thefuck
)

# zsh-completions
autoload -U compinit && compinit

# TODO: for gibo 
# mkdir -p $ZSH/custom/plugins/gibo/
# ln -s /path/to/gibo-completion.zsh $ZSH/custom/plugins/gibo/gibo.plugin.zsh

##############################################################################
# Plugins - Debug Load Time 
##############################################################################
PRINT_LOAD_TIME=false

if $PRINT_LOAD_TIME; then 
  for plugin ($plugins); do
    timer=$(($(gdate +%s%N)/1000000))
    if [ -f $ZSH_CUSTOM/plugins/$plugin/$plugin.plugin.zsh ]; then  
      source $ZSH_CUSTOM/plugins/$plugin/$plugin.plugin.zsh  
    elif [ -f $ZSH/plugins/$plugin/$plugin.plugin.zsh ]; then  
      source $ZSH/plugins/$plugin/$plugin.plugin.zsh  
    fi  
    now=$(($(gdate +%s%N)/1000000))
    elapsed=$(($now-$timer))  
    echo $elapsed":" $plugin  
  done 
fi 

timezsh() {
  shell=${1-$SHELL}
  for i in $(seq 1 10); do /usr/bin/time $shell -i -c exit; done
}

##############################################################################
# Plugins - OMZ INIT
##############################################################################
source $ZSH/oh-my-zsh.sh

# TODO: Cache
eval "$(direnv hook zsh)"

# TODO: [oh-my-zsh]     compaudit | xargs chmod g-w,o-w  permissions zsh 

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
