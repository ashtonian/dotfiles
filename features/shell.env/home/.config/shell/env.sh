# ~/.config/shell/env.sh - the environment every shell and agent gets.
#
# POSIX sh, sourced by ~/.zshenv (every zsh, including Codex's command shells
# before they hand off to bash), by ~/.bashrc (bash, including the shell Claude
# Code's Bash tool snapshots), and through BASH_ENV by the OpenCode server's
# commands. It runs that often, so it must stay idempotent, silent and
# fork-free: builtins only, no `brew shellenv`, no `mise activate`.
# Interactive-only setup (prompt, completions, mise's per-prompt PATH updates,
# zoxide, direnv) stays in the zsh modules.

# _env_drop DIR: remove every occurrence of DIR from PATH.
_env_drop() {
    _env_p=":$PATH:"
    while :; do
        case "$_env_p" in
            *":$1:"*) _env_p="${_env_p%%:"$1":*}:${_env_p#*:"$1":}" ;;
            *) break ;;
        esac
    done
    _env_p="${_env_p#:}"
    PATH="${_env_p%:}"
}

# _env_front DIR: put DIR first in PATH (moving it if present) when it exists.
_env_front() {
    [ -d "$1" ] || return 0
    _env_drop "$1"
    PATH="$1${PATH:+:$PATH}"
}

# _env_back DIR: append DIR to PATH when it exists and is not already there.
_env_back() {
    [ -d "$1" ] || return 0
    case ":$PATH:" in
        *":$1:"*) ;;
        *) PATH="${PATH:+$PATH:}$1" ;;
    esac
}

_env_vars() {
# Homebrew: what `brew shellenv` exports, without running brew.
for _env_d in /opt/homebrew /usr/local /home/linuxbrew/.linuxbrew "$HOME/.linuxbrew"; do
    if [ -x "$_env_d/bin/brew" ]; then
        HOMEBREW_PREFIX=$_env_d
        break
    fi
done
if [ -n "${HOMEBREW_PREFIX:-}" ]; then
    export HOMEBREW_PREFIX
    export HOMEBREW_CELLAR="$HOMEBREW_PREFIX/Cellar"
    if [ "$HOMEBREW_PREFIX" = /opt/homebrew ]; then
        export HOMEBREW_REPOSITORY="$HOMEBREW_PREFIX"
    else
        export HOMEBREW_REPOSITORY="$HOMEBREW_PREFIX/Homebrew"
    fi
    case ":${INFOPATH:-}:" in
        *":$HOMEBREW_PREFIX/share/info:"*) ;;
        *) export INFOPATH="$HOMEBREW_PREFIX/share/info:${INFOPATH:-}" ;;
    esac
fi

export GOPATH="${GOPATH:-$HOME/go}"
export PAGER="${PAGER:-less}"      # plain less; bat as PAGER mangles man pages
export LANG="${LANG:-en_US.UTF-8}" # LANG only; never force LC_ALL
export DOTFILES="${DOTFILES:-$HOME/.dotfiles}"
# zoxide's init-position check always warns (its plugin loads mid-.zshrc), and
# the warning prints in every non-interactive zsh.
export _ZO_DOCTOR=0
# Only zsh hands a marked command shell to bash (zshenv.zsh, zlogin.zsh); in
# any other shell the marker would make every `zsh -c` it starts run in bash.
[ -n "${ZSH_VERSION:-}" ] || unset AGENT_SHELL
}

# _env_late: what needs the composed PATH.
_env_late() {
if [ -z "${EDITOR:-}" ]; then
    if command -v nvim >/dev/null 2>&1; then EDITOR=nvim; else EDITOR=vim; fi
    export EDITOR
fi
export VISUAL="${VISUAL:-$EDITOR}"

# The enabled features' environment and exported settings (dotfiles apply),
# such as a host profile's PLAYWRIGHT_BROWSERS_PATH.
_env_g="$HOME/.config/dotfiles/generated/env.sh"
if [ -r "$_env_g" ]; then
    . "$_env_g"
fi
}

_env_path() {
# System directories, as /usr/libexec/path_helper would add them for a login shell.
for _env_f in /etc/paths /etc/paths.d/*; do
    [ -f "$_env_f" ] || continue
    while IFS= read -r _env_d || [ -n "$_env_d" ]; do
        [ -n "$_env_d" ] && _env_back "$_env_d"
    done < "$_env_f"
done

# Highest priority last. Language toolchains outrank Homebrew's generic copies,
# and the user's own bins outrank everything.
if [ -n "${HOMEBREW_PREFIX:-}" ]; then
    _env_front "$HOMEBREW_PREFIX/sbin"
    _env_front "$HOMEBREW_PREFIX/bin"
    _env_front "$HOMEBREW_PREFIX/opt/ruby/bin"
    _env_front "$HOMEBREW_PREFIX/opt/python/libexec/bin" # unversioned python, pip
    _env_front "$HOMEBREW_PREFIX/opt/openjdk/bin"
    _env_front "$HOMEBREW_PREFIX/opt/rustup/bin"         # keg-only rustup proxies
    for _env_d in "$HOMEBREW_PREFIX"/lib/ruby/gems/*/bin; do
        _env_back "$_env_d"
    done
fi
# mise's shims run the tool version each directory asks for (go.mod, .nvmrc,
# .python-version, mise.toml) in agents, LaunchAgents and GUI apps; interactive
# zsh puts the real tool directories in front of them.
_env_front "${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}/shims"
_env_front "$GOPATH/bin"
_env_front "$HOME/.local/bin"
_env_front "$HOME/bin"
_env_back "$HOME/.orbstack/bin"
_env_back "$HOME/.local/share/zinit/polaris/bin"
export PATH
export DOTFILES_ENV_PATH="$PATH"
}

# _env_added: the PATH entries something put there since this file last
# composed PATH (a virtualenv, a tool's own bin), in order. Entries under mise's
# data directory are mise's own: its prompt hook rewrites them in real sessions.
# path_helper's entries are system ones even where the directory is missing.
_env_added() {
    _env_x=''
    _env_mise="${MISE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/mise}"
    _env_sys=''
    for _env_f in /etc/paths /etc/paths.d/*; do
        [ -f "$_env_f" ] || continue
        while IFS= read -r _env_d || [ -n "$_env_d" ]; do
            _env_sys="$_env_sys:$_env_d"
        done < "$_env_f"
    done
    _env_rest="$PATH:"
    while [ -n "$_env_rest" ]; do
        _env_d=${_env_rest%%:*}
        _env_rest=${_env_rest#*:}
        case "$_env_d" in "" | "$_env_mise"/*) continue ;; esac
        case ":$DOTFILES_ENV_PATH:$_env_sys:" in *":$_env_d:"*) continue ;; esac
        case ":$_env_x:" in *":$_env_d:"*) continue ;; esac
        _env_x="${_env_x:+$_env_x:}$_env_d"
    done
}

# PATH is composed once per process tree. A nested shell whose PATH still ends
# with what this file produced keeps it as it is. Otherwise, after path_helper
# in a login shell, mise's prompt hook, or a program that reset PATH, it is
# composed again, with the entries something added since kept in front in their
# order, so a virtualenv activated before starting an agent stays first.
_env_main() {
_env_vars
_env_x=''
if [ -n "${DOTFILES_ENV_PATH:-}" ]; then
    case "$PATH" in
        "$DOTFILES_ENV_PATH" | *":$DOTFILES_ENV_PATH")
            _env_late
            return 0
            ;;
    esac
    _env_added
fi
# Out first, so DOTFILES_ENV_PATH records the composed PATH alone and the next
# shell recognises it with the added entries still in front.
_env_rest="$_env_x:"
while [ "$_env_rest" != ":" ] && [ -n "$_env_rest" ]; do
    _env_drop "${_env_rest%%:*}"
    _env_rest=${_env_rest#*:}
done
_env_path
if [ -n "$_env_x" ]; then
    PATH="$_env_x:$PATH"
    export PATH
fi
_env_late
}

# Claude Code also prepends this file to commands in sessions still running zsh,
# where an unmatched glob would abort the command; sh emulation passes it through.
if [ -n "${ZSH_VERSION:-}" ]; then
    emulate sh -c _env_main
else
    _env_main
fi
unset _env_p _env_f _env_d _env_g _env_x _env_rest _env_mise _env_sys
unset -f _env_main _env_vars _env_late _env_path _env_added _env_drop _env_front _env_back
