##############################################################################
# THEME - instant Prompt
##############################################################################
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
typeset -g POWERLEVEL9K_INSTANT_PROMPT=off

if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi


##############################################################################
# PATH
##############################################################################
export GOPATH=$HOME/go
export PATH=$GOPATH/bin:$PATH


export ZSH_WAKATIME_BIN=/opt/homebrew/bin/wakatime-cli

export PATH=$HOME/bin:$PATH
export PATH=/opt/homebrew/bin:$PATH
export PATH=/usr/local/bin:$PATH
export PATH=/usr/local/sbin:$PATH
export PATH=/usr/local/opt/python/libexec/bin:$PATH
export PATH="/usr/local/opt/openjdk/bin:$PATH"

## intel mac
if [ -d "/usr/local/opt/ruby/bin" ]; then
  export PATH=/usr/local/opt/ruby/bin:$PATH
  export PATH=`gem environment gemdir`/bin:$PATH
fi

## m1 mac
if [ -d "/opt/homebrew/opt/ruby/bin" ]; then
  export PATH=/opt/homebrew/opt/ruby/bin:$PATH
  export PATH=`gem environment gemdir`/bin:$PATH
fi

# Path to your oh-my-zsh installation.
export ZSH="$HOME/.oh-my-zsh"
# re-export this so it can be used to install custom plugins
export ZSH_CUSTOM="$ZSH/custom"

source $HOME/.dotfiles/lib_sh/funcs.sh

# alias python=/usr/bin/python3
# autoload -U +X compinit && compinit


##############################################################################
# Keybindings
##############################################################################
## iterm undo  https://stackoverflow.com/questions/6205157/iterm-2-how-to-set-keyboard-shortcuts-to-jump-to-beginning-end-of-line#answer-29403520
bindkey "^X^_" redo

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

if ! gem list colorls -i >/dev/null 2>&1; then
  echo "colorls gem not found, installing..."
  gem install colorls
fi


typeset -A custom_plugins

custom_plugins=(
"alias-tips" "https://github.com/djui/alias-tips.git"
"wakatime" "https://github.com/sobolevn/wakatime-zsh-plugin.git"
"autoupdate" "https://github.com/TamCore/autoupdate-oh-my-zsh-plugins"
"zsh-tab-colors" "https://github.com/tysonwolker/iterm-tab-colors.git "
"zsh-256color" "https://github.com/chrissicool/zsh-256color"
"zsh-autosuggestions" "https://github.com/zsh-users/zsh-autosuggestions"
"zsh-completions" "https://github.com/zsh-users/zsh-completions"
"zsh-diff-so-fancy" "https://github.com/z-shell/zsh-diff-so-fancy"
"fast-alias-tips" "https://github.com/sei40kr/zsh-fast-alias-tips.git"
"zsh-fzy" "https://github.com/aperezdc/zsh-fzy"
"zsh-syntax-highlighting" "https://github.com/zsh-users/zsh-syntax-highlighting.git"
"autopair" "https://github.com/hlissner/zsh-autopair"
"auto-color-ls" "https://github.com/gretzky/auto-color-ls"
"zsh-autoquoter" "https://github.com/ianthehenry/zsh-autoquoter.git"
"colorize" "https://github.com/zpm-zsh/colorize"
"git-it-on" "https://github.com/peterhurford/git-it-on.zsh"
)

for key val in ${(kv)custom_plugins}; do
    dir="$ZSH_CUSTOM/plugins/$key"
  if [[ ! -d $dir ]] || [ -z "$(ls -A "$dir")" ]; then
    git clone $val $dir
  fi
done

if ! command -v def-matcher &> /dev/null
then
  mv "$ZSH_CUSTOM/plugins/fast-alias-tips/def-matcher.go" "$ZSH_CUSTOM/plugins/fast-alias-tips/main.go"
  go build -c "$ZSH_CUSTOM/plugins/fast-alias-tips" -o "$GOPATH/bin/def-matcher"
fi

if [[ ! -d "$ZSH_CUSTOM/plugins/gibo" ]] || [ -z "$(ls -A "$ZSH_CUSTOM/plugins/gibo")" ]; then
    mkdir -p $ZSH_CUSTOM/plugins/gibo/
    ln -s /opt/homebrew/share/zsh/site-functions/_gibo $ZSH_CUSTOM/plugins/gibo/gibo.plugin.zsh
fi

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
    # kubectl
    node
    nvm
    macos
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
    colored-man-pages
    vscode
    web-search
    wakatime
    z
    zsh-interactive-cd

    # ###### Custom ####################################
    wakatime
    colorize
    autoupdate
    # zsh-tab-colors #see pr https://github.com/tysonwolker/iterm-tab-colors/pull/14 -> workaroun
    zsh-256color
    zsh-autosuggestions
    zsh-Diff-So-Fancy
    fast-alias-tips
    zsh-fzy
    zsh-syntax-highlighting
    # # zsh-thefuck
    gibo
    autopair
    auto-color-ls
    git-it-on
    # TODO: fzf
)

# zsh-completions
fpath+=${ZSH_CUSTOM:-${ZSH:-~/.oh-my-zsh}/custom}/plugins/zsh-completions/src

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

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh


##############################################################################
# Completions & Evals
##############################################################################

# must be after source omz
autoload -U compinit && compinit

eval $(/opt/homebrew/bin/brew shellenv)
source <(helm completion zsh)
eval "$(fnm env)"
# source <(kubectl completion zsh)
source /opt/homebrew/opt/git-extras/share/git-extras/git-extras-completion.zsh
eval "$(direnv hook zsh)"

## REORG
# Uncomment the following line to change how often to auto-update (in days).
# export UPDATE_ZSH_DAYS=13
#ZSH_CUSTOM_AUTOUPDATE_QUIET=true

#!/usr/bin/zsh
#!/usr/bin/zsh

# List of commands and their parameters
#Frogs

animals=(
blowfish
dragon-and-cow
hellokitty
milk
smallturkey
bong
dragon
kiss
moofasa
turtle
bud-frogs
elephant-in-snake
kitty
moose
stegosaurus
tux
bunnyelephant
koala
mutilated
stimpy
udder
cheese
eyes
kosh
ren
supermilker
vader-koala
luke-koala
satanic
surgery
vader
daemon
ghostbusters
sheep
telebears
www
beavis.zen
default
head-in
meow
skeleton
three-eyes
)

quotes=(
  "fortune -s computers"
)

quote=${quotes[$RANDOM % $#quotes + 1]}
animal=${animals[$RANDOM % $#animals + 1]}
eval $quote | cowsay -f $animal | lolcat #-a -d 1

# Define aliases to add in the format of "<alias>" "<command> args..."
typeset -A aliases_to_add=(
  "ping" "prettyping --nolegend"
  "hosts" "prettyping --nolegend --noclear --hosts"
  "cat" "bat"
  "top" "htop"
  "du" "ncdu --color dark -rr -x --exclude .git --exclude node_modules"
  "grep" "ggrep --color=auto --exclude-dir={.bzr,CVS,.git,.hg,.svn}"
  "ls" "colorls"
)
# Create the aliases_to_add for the corresponding commands if the aliased command exists
for alias_name command_with_args in ${(kv)aliases_to_add}; do
  # Split the command with arguments into separate variables
  command_name="${command_with_args%% *}"
  if command -v "$command_name" &> /dev/null; then
    alias "$alias_name"="$command_with_args"
  fi

done
