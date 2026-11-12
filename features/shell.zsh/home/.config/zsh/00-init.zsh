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

#=============================================================================
# CACHED INIT SCRIPTS
#=============================================================================
# _dotfiles_cached_eval NAME [-e VAR]... COMMAND [ARGS...]: source what COMMAND
# prints, as `eval "$(COMMAND ARGS)"` would, without starting it on every shell.
# Only for output that depends on nothing but the binary, the arguments and the
# variables named with -e. The cache under $XDG_CACHE_HOME/zsh starts with the
# resolved binary, the arguments and those values, so an upgrade (a new Cellar
# path) or a change to any of them regenerates it; a bottle's file times can
# predate the cache, so modification times alone would miss one.
_dotfiles_cached_eval() {
    local name=$1; shift
    local -a envs
    while [[ $1 == -e ]]; do
        envs+=("$2=${(P)2-}")
        shift 2
    done
    local bin=${commands[$1]:-}
    [[ -n $bin ]] || return 0
    local cache=${XDG_CACHE_HOME:-$HOME/.cache}/zsh/init-$name.zsh
    local stamp="# ${bin:A} ${*:2} | ${(j: :)envs}" first=''
    [[ -s $cache ]] && IFS= read -r first < $cache
    if [[ $first != $stamp || $bin -nt $cache ]]; then
        command mkdir -p ${cache:h}
        if ! { print -r -- $stamp && "$@" } >| $cache.$$ 2>/dev/null; then
            command rm -f $cache.$$
            return 1
        fi
        command mv -f $cache.$$ $cache
    fi
    source $cache
}

#=============================================================================
# CORE ZSH OPTIONS
#=============================================================================
# cd by typing a directory name; in a tool shell a word that happens to name a
# directory would change directory instead of failing.
[[ "${ZSH_REAL_SESSION:-0}" == 1 ]] && setopt AUTO_CD
setopt AUTO_PUSHD           # Push directories onto stack
setopt PUSHD_IGNORE_DUPS    # Don't push duplicates
setopt PUSHD_SILENT         # Don't print directory stack
# setopt CORRECT            # disabled: disruptive "did you mean" prompts on typos
setopt INTERACTIVE_COMMENTS # Allow comments in interactive shell
setopt NO_BEEP              # No beeping
