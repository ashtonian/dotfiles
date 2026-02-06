# 00-init.zsh - Zinit initialization
# This file bootstraps zinit and sets up core zsh options

#=============================================================================
# ZINIT INSTALLATION (auto-installs if missing)
#=============================================================================
ZINIT_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/zinit/zinit.git"

if [[ ! -d "$ZINIT_HOME" ]]; then
    print -P "%F{33}▓▒░ %F{220}Installing zinit...%f"
    command mkdir -p "$(dirname $ZINIT_HOME)"
    command git clone https://github.com/zdharma-continuum/zinit.git "$ZINIT_HOME" && \
        print -P "%F{33}▓▒░ %F{34}Installation successful.%f%b" || \
        print -P "%F{160}▓▒░ Clone failed.%f%b"
fi

source "${ZINIT_HOME}/zinit.zsh"

# Load zinit annexes for extended functionality
zinit light-mode for \
    zdharma-continuum/zinit-annex-bin-gem-node \
    zdharma-continuum/zinit-annex-patch-dl

#=============================================================================
# CORE ZSH OPTIONS
#=============================================================================
setopt AUTO_CD              # cd by typing directory name
setopt AUTO_PUSHD           # Push directories onto stack
setopt PUSHD_IGNORE_DUPS    # Don't push duplicates
setopt PUSHD_SILENT         # Don't print directory stack
setopt CORRECT              # Command correction
setopt INTERACTIVE_COMMENTS # Allow comments in interactive shell
setopt NO_BEEP              # No beeping
